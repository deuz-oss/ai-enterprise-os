"""Fase 10 lanjutan — Kas & Bank, Pembelian, Aset Tetap, Arus Kas (PRD §8.4/8.7)."""

import uuid as _uuid
from calendar import monthrange
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.accounting.models import (
    Account,
    BankTransaction,
    BankTxType,
    BillStatus,
    FixedAsset,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    PurchaseBill,
)
from app.modules.accounting.service import income_statement, post_auto_event
from app.modules.accounting.transactions_schemas import APAgingRow


def _get_bank_account(db: Session, account_id) -> Account:
    acc = db.get(Account, parse_uuid(str(account_id)))
    if acc is None or not acc.is_cash_bank:
        raise HTTPException(
            status_code=422,
            detail="Akun kas & bank tidak valid (wajib akun ber-flag is_cash_bank)",
        )
    return acc


def create_bank_transaction(
    db: Session,
    *,
    tx_type: str,
    bank_account_id,
    amount: float,
    tx_date: date | None = None,
    counter_account_id=None,
    description: str | None = None,
) -> BankTransaction:
    """Transaksi kas/bank; jurnal otomatis dibentuk sesuai arah mutasi."""
    bank = _get_bank_account(db, bank_account_id)
    counter = db.get(Account, parse_uuid(str(counter_account_id))) if counter_account_id else None
    try:
        direction = BankTxType(tx_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Tipe transaksi harus penerimaan/pembayaran/transfer_antar_rekening",
        ) from None
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Nominal harus > 0")
    amt = round(amount)

    if direction == BankTxType.receipt:
        event = "cash_receipt"
        lines = [(bank.code, amt, 0.0), (counter.code if counter else "4-1000", 0.0, amt)]
    elif direction == BankTxType.payment:
        event = "cash_payment"
        lines = [(counter.code if counter else "5-9000", amt, 0.0), (bank.code, 0.0, amt)]
    else:
        event = "bank_transfer"
        if counter is None or not counter.is_cash_bank:
            raise HTTPException(
                status_code=422,
                detail="Transfer antar rekening: akun lawan juga wajib akun kas & bank",
            )
        lines = [(bank.code, amt, 0.0), (counter.code, 0.0, amt)]

    tx = BankTransaction(
        tx_type=direction,
        bank_account_id=bank.id,
        counter_account_id=counter.id if counter else None,
        amount=amt,
        tx_date=tx_date or date.today(),
        description=(description or "").strip()[:500] or None,
    )
    db.add(tx)
    db.flush()
    entry = post_auto_event(
        db,
        tenant_id=tx.tenant_id,
        event_code=event,
        source_ref_type="bank_transaction",
        source_ref_id=tx.id,
        entry_date=tx.tx_date,
        description=f"{direction.value}: {tx.description or ''}".strip(),
        lines=lines,
    )
    tx.journal_entry_id = entry.id if entry else None
    db.commit()
    db.refresh(tx)
    audit.log_event(
        db,
        action="bank_transaction.created",
        entity_type="bank_transaction",
        entity_id=tx.id,
        detail={"type": tx.tx_type.value, "amount": float(tx.amount)},
    )
    return tx


def list_bank_transactions(
    db: Session, year: int, month: int | None = None, reconciled: bool | None = None
) -> list[BankTransaction]:
    stmt = select(BankTransaction).order_by(BankTransaction.tx_date.desc())
    stmt = stmt.where(func.extract("year", BankTransaction.tx_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", BankTransaction.tx_date) == month)
    if reconciled is True:
        stmt = stmt.where(BankTransaction.reconciled_at.is_not(None))
    elif reconciled is False:
        stmt = stmt.where(BankTransaction.reconciled_at.is_(None))
    return list(db.execute(stmt).scalars())


def reconcile_bank_transaction(db: Session, user, tx_id: str) -> BankTransaction:
    """Rekonsiliasi manual: cocok dengan rekening koran."""
    tx = db.get(BankTransaction, parse_uuid(tx_id))
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if tx.reconciled_at is None:
        tx.reconciled_at = datetime.now(UTC)
        db.commit()
        db.refresh(tx)
        audit.log_event(
            db,
            action="bank_transaction.reconciled",
            entity_type="bank_transaction",
            entity_id=tx.id,
            detail={"by": getattr(user, "email", "?")},
        )
    return tx


# ---------- Pembelian ----------


def create_purchase_bill(db: Session, payload) -> PurchaseBill:
    """Bill vendor diterima → Dr Beban/Aset + Dr PPN Masukan / Cr Utang Usaha."""
    expense = db.get(Account, parse_uuid(str(payload.expense_account_id)))
    if expense is None or not expense.is_active:
        raise HTTPException(status_code=422, detail="Akun beban/aset tidak valid")
    ppn_amount = round(payload.amount * payload.ppn_rate)

    bill = PurchaseBill(
        vendor_name=payload.vendor_name,
        bill_number=payload.bill_number,
        expense_account_id=expense.id,
        amount=payload.amount,
        ppn_rate=payload.ppn_rate,
        ppn_amount=ppn_amount,
        entry_date=payload.entry_date or date.today(),
        due_date=payload.due_date,
        notes=payload.notes,
        status=BillStatus.unpaid,
    )
    db.add(bill)
    db.flush()

    total_cr = round(payload.amount + ppn_amount)
    lines = [(expense.code, round(payload.amount), 0.0)]
    if ppn_amount:
        lines.append(("1-1400", ppn_amount, 0.0))
    lines.append(("2-1000", 0.0, total_cr))

    entry = post_auto_event(
        db,
        tenant_id=bill.tenant_id,
        event_code="purchase_received",
        source_ref_type="purchase_bill",
        source_ref_id=bill.id,
        entry_date=bill.entry_date,
        description=f"Bill {payload.vendor_name}",
        lines=lines,
    )
    bill.received_journal_id = entry.id if entry else None
    db.commit()
    db.refresh(bill)
    audit.log_event(
        db,
        action="purchase_bill.received",
        entity_type="purchase_bill",
        entity_id=bill.id,
        detail={"vendor": bill.vendor_name, "amount": float(bill.amount)},
    )
    return bill


def pay_purchase_bill(
    db: Session, *, bill_id: str, bank_account_id, paid_date: date | None = None
) -> PurchaseBill:
    """Bayar bill → Dr Utang Usaha / Cr Kas-Bank."""
    bill = db.get(PurchaseBill, parse_uuid(bill_id))
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill tidak ditemukan")
    if bill.status == BillStatus.paid:
        raise HTTPException(status_code=409, detail="Bill sudah dibayar")
    bank = _get_bank_account(db, bank_account_id)

    total = round(float(bill.amount) + float(bill.ppn_amount))
    entry = post_auto_event(
        db,
        tenant_id=bill.tenant_id,
        event_code="purchase_paid",
        source_ref_type="purchase_bill",
        source_ref_id=bill.id,
        entry_date=paid_date or date.today(),
        description=f"Pelunasan bill {bill.vendor_name}",
        lines=[("2-1000", total, 0.0), (bank.code, 0.0, total)],
    )
    bill.status = BillStatus.paid
    bill.paid_journal_id = entry.id if entry else None
    db.commit()
    db.refresh(bill)
    audit.log_event(
        db,
        action="purchase_bill.paid",
        entity_type="purchase_bill",
        entity_id=bill.id,
        detail={"total": total},
    )
    return bill


def list_purchase_bills(db: Session, status: BillStatus | None = None) -> list[PurchaseBill]:
    stmt = select(PurchaseBill).order_by(PurchaseBill.entry_date.desc())
    if status is not None:
        stmt = stmt.where(PurchaseBill.status == status)
    return list(db.execute(stmt).scalars())


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    return ">60"


def ap_aging_report(db: Session) -> list[APAgingRow]:
    """Bill vendor belum dibayar yang melewati jatuh tempo, per bucket umur.

    Cermin `finance/service.py::aging_report()` (sisi AR) — `_aging_bucket()`
    sengaja diduplikasi (bukan di-share) karena 5 baris logic murni tidak
    sepadan dengan coupling cross-module baru antara accounting<->finance.
    """
    stmt = (
        select(PurchaseBill)
        .where(PurchaseBill.status == BillStatus.unpaid)
        .where(PurchaseBill.due_date.is_not(None))
        .where(PurchaseBill.due_date < date.today())
        .order_by(PurchaseBill.due_date)
    )
    today = date.today()
    rows: list[APAgingRow] = []
    for bill in db.execute(stmt).scalars():
        days_overdue = (today - bill.due_date).days  # type: ignore[operator]
        rows.append(
            APAgingRow(
                bill_id=bill.id,
                bill_number=bill.bill_number,
                vendor_name=bill.vendor_name,
                total_due=float(bill.amount) + float(bill.ppn_amount),
                due_date=bill.due_date,  # type: ignore[arg-type]
                days_overdue=days_overdue,
                bucket=_aging_bucket(days_overdue),
            )
        )
    return rows


# ---------- Aset tetap ----------


def acquire_fixed_asset(db: Session, payload) -> FixedAsset:
    """Perolehan aset → Dr Aset Tetap / Cr sumber dana (default Bank)."""
    funding = (
        db.get(Account, parse_uuid(str(payload.funding_account_id)))
        if payload.funding_account_id
        else None
    )
    asset_acc = db.get(Account, parse_uuid(str(payload.asset_account_id)))
    if asset_acc is None:
        raise HTTPException(status_code=422, detail="Akun aset tetap tidak valid")
    funding_code = funding.code if funding else "1-1100"

    monthly = round(float(payload.cost) / max(payload.useful_life_months, 1))
    asset = FixedAsset(
        name=payload.name,
        asset_account_id=asset_acc.id,
        accum_depreciation_account_id=_acc_id(db, "1-2100"),
        depreciation_expense_account_id=_acc_id(db, "5-6000"),
        funding_account_id=funding.id if funding else None,
        acquisition_date=payload.acquisition_date or date.today(),
        cost=payload.cost,
        useful_life_months=payload.useful_life_months,
        monthly_depreciation=monthly,
        notes=payload.notes,
    )
    db.add(asset)
    db.flush()
    post_auto_event(
        db,
        tenant_id=asset.tenant_id,
        event_code="asset_acquired",
        source_ref_type="fixed_asset",
        source_ref_id=asset.id,
        entry_date=asset.acquisition_date,
        description=f"Perolehan aset: {asset.name}",
        lines=[
            (asset_acc.code, round(payload.cost), 0.0),
            (funding_code, 0.0, round(payload.cost)),
        ],
    )
    db.commit()
    db.refresh(asset)
    audit.log_event(
        db,
        action="fixed_asset.acquired",
        entity_type="fixed_asset",
        entity_id=asset.id,
        detail={"name": asset.name, "cost": float(asset.cost)},
    )
    return asset


def _acc_id(db: Session, code: str):
    acc = db.get(Account, parse_uuid(code)) if code else None
    if acc is None:
        acc = get_account_by_code(db, code)
    return acc.id if acc else None


def get_account_by_code(db: Session, code: str):
    return db.execute(select(Account).where(Account.code == code)).scalar_one_or_none()


def _acc_code_of(db: Session, account_id) -> str:
    acc = db.get(Account, account_id)
    return acc.code if acc else "5-9000"


def depreciate_asset_monthly(db: Session, *, asset_id: str, year: int, month: int):
    """Penyusutan bulanan idempoten per aset per bulan (garis lurus).

    Nominal dibatasi sisa nilai buku.
    """
    asset = db.get(FixedAsset, parse_uuid(asset_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if asset.disposed_at is not None:
        raise HTTPException(status_code=409, detail="Aset sudah didisposisi")
    ym = f"{year}-{str(month).zfill(2)}"
    if asset.last_depreciated_ym == ym:
        raise HTTPException(status_code=409, detail=f"Penyusutan {ym} sudah dicatat")

    book = float(asset.cost) - float(asset.accumulated_depreciation)
    dep = int(min(float(asset.monthly_depreciation), max(book, 0)))

    ref_id = _uuid.uuid5(_uuid.NAMESPACE_OID, f"dep:{asset.id}:{ym}")
    last_day = monthrange(year, month)[1]
    entry = post_auto_event(
        db,
        tenant_id=asset.tenant_id,
        event_code="depreciation_monthly",
        source_ref_type="fixed_asset_dep",
        source_ref_id=ref_id,
        entry_date=date(year, month, min(28, last_day)),
        description=f"Penyusutan {asset.name} periode {ym}",
        lines=[
            (_acc_code_of(db, asset.depreciation_expense_account_id), dep, 0.0),
            (_acc_code_of(db, asset.accum_depreciation_account_id), 0.0, dep),
        ],
    )
    asset.last_depreciated_ym = ym
    asset.accumulated_depreciation = float(asset.accumulated_depreciation) + dep
    db.commit()
    db.refresh(asset)
    audit.log_event(
        db,
        action="fixed_asset.depreciated",
        entity_type="fixed_asset",
        entity_id=asset.id,
        detail={"ym": ym, "amount": dep},
    )
    return asset, dep, entry.id if entry else None


def _pending_depreciation_assets(db: Session, *, year: int, month: int) -> list[FixedAsset]:
    """Aset tetap yang belum disusutkan periode ini dan masih punya nilai
    buku tersisa (fully-depreciated tidak akan pernah punya jurnal baru,
    nominalnya 0 — difilter supaya tidak selamanya muncul sebagai "pending")."""
    ym = f"{year}-{str(month).zfill(2)}"
    last_day = monthrange(year, month)[1]
    return list(
        db.execute(
            select(FixedAsset).where(
                FixedAsset.disposed_at.is_(None),
                FixedAsset.acquisition_date <= date(year, month, last_day),
                (FixedAsset.last_depreciated_ym.is_(None)) | (FixedAsset.last_depreciated_ym != ym),
                FixedAsset.cost - FixedAsset.accumulated_depreciation > 0,
            )
        ).scalars()
    )


def depreciate_period(db: Session, *, year: int, month: int) -> dict:
    """Jalankan penyusutan bulanan untuk semua aset eligible sekaligus.

    Tiap aset diproses independen — kegagalan satu aset (409 aset sudah
    disposisi, dsb, ditangkap per-iterasi) tidak menghentikan batch, pola
    yang sama seperti `bank_statement.import_statement()`.
    """
    assets = _pending_depreciation_assets(db, year=year, month=month)
    posted: list[str] = []
    skipped: list[dict] = []
    for asset in assets:
        try:
            depreciate_asset_monthly(db, asset_id=str(asset.id), year=year, month=month)
            posted.append(asset.name)
        except HTTPException as exc:
            skipped.append({"asset": asset.name, "reason": exc.detail})
    return {"posted": posted, "skipped": skipped}


def dispose_fixed_asset(
    db: Session, *, asset_id: str, proceeds: float = 0.0, disposed_date: date | None = None
) -> FixedAsset:
    """Disposisi: hapus nilai buku; selisih masuk pendapatan/beban lain."""
    asset = db.get(FixedAsset, parse_uuid(asset_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if asset.disposed_at is not None:
        raise HTTPException(status_code=409, detail="Aset sudah didisposisi")
    disposed_date = disposed_date or date.today()

    book_value = float(asset.cost) - float(asset.accumulated_depreciation)
    gain = float(proceeds) - book_value

    final_lines: list[tuple[str, float, float]] = []
    if proceeds:
        final_lines.append(("1-1100", round(proceeds), 0.0))
    final_lines.append(
        (
            _acc_code_of(db, asset.accum_depreciation_account_id),
            float(asset.accumulated_depreciation),
            0.0,
        )
    )
    final_lines.append((_acc_code_of(db, asset.asset_account_id), 0.0, float(asset.cost)))
    if gain > 0:
        final_lines.append(("4-9000", 0.0, round(gain)))
    elif gain < 0:
        final_lines.append(("6-1000", round(-gain), 0.0))

    ref = _uuid.uuid5(_uuid.NAMESPACE_OID, f"dispose:{asset.id}")
    post_auto_event(
        db,
        tenant_id=asset.tenant_id,
        event_code="asset_disposed",
        source_ref_type="fixed_asset_disposal",
        source_ref_id=ref,
        entry_date=disposed_date,
        description=f"Disposisi aset: {asset.name}",
        lines=final_lines,
    )
    asset.disposed_at = disposed_date
    asset.disposal_proceeds = proceeds
    db.commit()
    db.refresh(asset)
    audit.log_event(
        db,
        action="fixed_asset.disposed",
        entity_type="fixed_asset",
        entity_id=asset.id,
        detail={"proceeds": proceeds, "book_value": book_value},
    )
    return asset


def list_fixed_assets(db: Session, include_disposed: bool = False) -> list[FixedAsset]:
    stmt = select(FixedAsset).order_by(FixedAsset.created_at.desc())
    if not include_disposed:
        stmt = stmt.where(FixedAsset.disposed_at.is_(None))
    return list(db.execute(stmt).scalars())


# ---------- Arus kas metode tidak langsung (PRD §8.7) ----------


def _balances_at(db: Session, until: date) -> dict[str, float]:
    """Saldo normal per 'grup|kode' dari jurnal posted s.d. tanggal.

    `until` harus objek date (bukan str) -- Postgres menolak perbandingan
    date <= character varying (SQLite lolos, tidak menegakkan tipe kolom).
    """
    effective_code = func.coalesce(Account.code, JournalLine.account_code)
    stmt = (
        select(
            Account.group_type,
            Account.is_cash_bank,
            effective_code,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .outerjoin(Account, JournalLine.account_id == Account.id)
        .where(
            JournalEntry.status == JournalEntryStatus.posted,
            JournalEntry.entry_date <= until,
        )
        .group_by(Account.group_type, Account.is_cash_bank, effective_code)
    )
    result: dict[str, float] = {}
    for group, is_cash, code, debit, credit in db.execute(stmt).all():
        gv = group.value if hasattr(group, "value") else str(group)
        cash_flag = "_cash" if is_cash else ""
        normal_debit = gv.startswith("aset") or gv in ("hpp", "beban_usaha", "beban_lain")
        result[f"{gv}|{code}{cash_flag}"] = (
            float(debit) - float(credit) if normal_debit else float(credit) - float(debit)
        )
    return result


def _is_cash_key(key: str) -> bool:
    return key.endswith("_cash")


def _delta_non_cash(
    prev: dict[str, float], now: dict[str, float], groups: tuple[str, ...]
) -> float:
    """Kenaikan saldo grup, MENGECUALIKAN akun kas & bank."""
    keys = set(prev) | set(now)
    total = 0.0
    for key in keys:
        gv = key.split("|", 1)[0]
        if gv not in groups or _is_cash_key(key):
            continue
        total += now.get(key, 0.0) - prev.get(key, 0.0)
    return round(total, 2)


def _delta_incl_cash(
    prev: dict[str, float], now: dict[str, float], groups: tuple[str, ...]
) -> float:
    """Kenaikan saldo grup TERMASUK kas & bank."""
    keys = set(prev) | set(now)
    total = 0.0
    for key in keys:
        gv = key.split("|", 1)[0]
        if gv not in groups:
            continue
        total += now.get(key, 0.0) - prev.get(key, 0.0)
    return round(total, 2)


def cash_flow_indirect(db: Session, year: int) -> dict:
    """Arus kas metode tidak langsung dari perubahan saldo akun.

    Net Change Cash = CFO + CFI + CFF (harus cocok dengan Δ saldo kas-bank).
    """
    prev = _balances_at(db, date(year - 1, 12, 31))
    now = _balances_at(db, date(year, 12, 31))

    net_income = income_statement(db, year=year).net_income

    # Penyusutan tahun berjalan = kenaikan akumulasi penyusutan.
    dep_start = sum(v for k, v in prev.items() if k.startswith("aset_tetap|") and "1-2100" in k)
    dep_end = sum(v for k, v in now.items() if k.startswith("aset_tetap|") and "1-2100" in k)
    depreciation = round(dep_end - dep_start, 2)

    # Non-cash aset lancar (piutang dll — tanpa kas & bank).
    wc_delta = _delta_non_cash(prev, now, ("aset_lancar",))
    liab_delta = _delta_incl_cash(prev, now, ("liabilitas_pendek", "liabilitas_panjang"))
    capex = _delta_non_cash(prev, now, ("aset_tetap",))

    # Ekuitas di luar laba tahun berjalan (modal & laba ditahan).
    equity_all = _delta_incl_cash(prev, now, ("ekuitas",))
    retained_keys = [k for k in set(prev) | set(now) if k.endswith("|3-3000")]
    retained_delta = round(sum(now.get(k, 0.0) - prev.get(k, 0.0) for k in retained_keys), 2)
    cff = round(equity_all - retained_delta, 2)

    cfo = round(net_income + depreciation - wc_delta + liab_delta, 2)
    cfi = round(-capex, 2)
    net_change = round(cfo + cfi + cff, 2)

    return {
        "year": year,
        "operating_activities": {
            "net_income": net_income,
            "add_depreciation": depreciation,
            "working_capital_change": round(-wc_delta, 2),
            "liabilities_change": liab_delta,
            "net_operating": cfo,
        },
        "investing_activities": {"capex_fixed_assets": cfi, "net_investing": cfi},
        "financing_activities": {
            "owner_contributions_and_borrowings": cff,
            "net_financing": cff,
        },
        "net_change_cash": net_change,
    }
