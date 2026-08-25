"""Fase 10 — Accounting ala Accurate: COA dinamis, periode, memorial→posted,
mesin auto-journal idempoten, dan laporan berbasis akun DB.

Aturan arsitektur (PRD §8.2): modul lain TIDAK boleh menulis tabel jurnal
langsung — hanya melalui `post_auto_event`.
"""

from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules.accounting.coa_template import DEFAULT_COA
from app.modules.accounting.models import (
    Account,
    AccountingPeriod,
    GroupType,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    JournalRule,
)
from app.modules.accounting.schemas import (
    BalanceSheet,
    BalanceSheetSection,
    IncomeStatement,
    IncomeStatementRow,
    JournalEntryIn,
    TrialBalanceRow,
)

BALANCE_GROUPS = ("aset_lancar", "aset_tetap", "liabilitas_pendek", "liabilitas_panjang", "ekuitas")
REVENUE_GROUPS = ("pendapatan", "pendapatan_lain")
EXPENSE_GROUPS = ("hpp", "beban_usaha", "beban_lain")


# ---------- Bagan akun ----------


def ensure_coa(db: Session, tenant_id) -> None:
    """Seed bagan akun + rules default untuk tenant (idempoten)."""
    from app.core.tenancy import get_tenant

    prev = get_tenant()
    set_tenant(tenant_id)
    try:
        existing = (
            db.execute(select(Account.code).where(Account.tenant_id == parse_uuid(str(tenant_id))))
            .scalars()
            .all()
        )
        if not existing:
            for code, name, group, normal, cash, ar_ap in DEFAULT_COA:
                db.add(
                    Account(
                        code=code,
                        name=name,
                        group_type=GroupType(group),
                        normal_balance=normal,
                        is_cash_bank=cash,
                        is_control_ar_ap=ar_ap,
                    )
                )
            db.commit()
        rule_count = db.scalar(
            select(func.count(JournalRule.id)).where(
                JournalRule.tenant_id == parse_uuid(str(tenant_id))
            )
        )
        if not rule_count:
            for event, d, c in _default_rules():
                db.add(
                    JournalRule(
                        tenant_id=parse_uuid(str(tenant_id)),
                        event_code=event,
                        debit_account_code=d,
                        credit_account_code=c,
                    )
                )
            db.commit()
    finally:
        set_tenant(prev)


def set_tenant(tenant_id) -> None:
    from app.core.tenancy import set_tenant as _set

    _set(parse_uuid(str(tenant_id)) if tenant_id else None)


def _default_rules():
    from app.modules.accounting.coa_template import DEFAULT_RULES

    return DEFAULT_RULES


def list_accounts(db: Session, include_inactive: bool = False):
    stmt = select(Account).order_by(Account.code)
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(db.execute(stmt).scalars())


def get_account_by_code(db: Session, code: str) -> Account | None:
    return db.execute(select(Account).where(Account.code == code)).scalar_one_or_none()


def _get_account_or_404(db: Session, account_id: str) -> Account:
    acc = db.get(Account, parse_uuid(account_id))
    if acc is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return acc


def create_account(db: Session, payload) -> Account:
    duplicate = get_account_by_code(db, payload.code)
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Kode akun sudah dipakai")
    account = Account(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: str, payload) -> Account:
    account = _get_account_or_404(db, account_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: str) -> None:
    account = _get_account_or_404(db, account_id)
    mutated = db.scalar(
        select(func.count(JournalLine.id)).where(JournalLine.account_id == account.id)
    )
    if mutated:
        raise HTTPException(
            status_code=409,
            detail="Akun sudah memiliki mutasi jurnal — nonaktifkan saja (jangan dihapus)",
        )
    db.delete(account)
    db.commit()


# ---------- Periode & tutup buku ----------


def assert_period_open(db: Session, entry_date: date) -> None:
    """Input backdate ke periode tertutup ditolak (PRD §8.5)."""
    closed = db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.year == entry_date.year,
            AccountingPeriod.month == entry_date.month,
        )
    ).scalar_one_or_none()
    if closed is not None:
        raise HTTPException(
            status_code=422,
            detail=f"Periode {entry_date.month}/{entry_date.year} sudah ditutup buku",
        )


def list_periods(db: Session) -> list[AccountingPeriod]:
    return list(
        db.execute(
            select(AccountingPeriod).order_by(
                AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
            )
        ).scalars()
    )


def close_period(
    db: Session, user, year: int, month: int, note: str | None = None
) -> AccountingPeriod:
    memorial_count = db.scalar(
        select(func.count(JournalEntry.id))
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(
            func.extract("year", JournalEntry.entry_date) == year,
            func.extract("month", JournalEntry.entry_date) == month,
            JournalEntry.status == JournalEntryStatus.memorial,
        )
    )
    if memorial_count:
        raise HTTPException(
            status_code=422,
            detail=f"Masih ada {memorial_count} jurnal memorial pada periode ini — posting dulu",
        )
    period = db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.year == year, AccountingPeriod.month == month
        )
    ).scalar_one_or_none()
    if period is None:
        period = AccountingPeriod(year=year, month=month)
        db.add(period)
    period.closed_by_id = getattr(user, "id", None)
    period.closed_at = datetime.now(UTC)
    period.notes = (note or "").strip()[:500] or None
    db.commit()
    db.refresh(period)
    return period


def reopen_period(db: Session, user, year: int, month: int) -> None:
    period = db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.year == year, AccountingPeriod.month == month
        )
    ).scalar_one_or_none()
    if period is not None:
        db.delete(period)
        db.commit()
        from app.modules import audit

        audit.log_event(
            db,
            action="accounting.period_reopened",
            entity_type="accounting_period",
            detail={"period": f"{month}/{year}", "by": getattr(user, "email", "?")},
        )


# ---------- Jurnal umum ----------


def create_entry(db: Session, payload: JournalEntryIn) -> JournalEntry:
    entry_date = payload.entry_date or date.today()
    assert_period_open(db, entry_date)

    entry = JournalEntry(
        entry_date=entry_date,
        description=payload.description,
        reference=payload.reference,
        status=(
            JournalEntryStatus.memorial
            if payload.status == "memorial"
            else JournalEntryStatus.posted
        ),
        posted_at=datetime.now(UTC) if payload.status != "memorial" else None,
    )
    for line in payload.lines:
        account = get_account_by_code(db, line.account_code)
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=422,
                detail=f"Kode akun tidak dikenal / tidak aktif: {line.account_code}",
            )
        entry.lines.append(
            JournalLine(
                account_code=line.account_code,
                account_id=account.id,
                debit=line.debit,
                credit=line.credit,
                client_dim_id=line.client_dim_id,
                memo=(line.memo or "")[:200] or None,
            )
        )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def post_entry(db: Session, entry_id: str) -> JournalEntry:
    """Memorial → posted dengan validasi PRD §8.2."""
    entry = db.get(JournalEntry, parse_uuid(entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Jurnal tidak ditemukan")
    if entry.status == JournalEntryStatus.posted:
        raise HTTPException(status_code=409, detail="Jurnal sudah terposting")

    total_debit = sum(float(l.debit) for l in entry.lines)  # noqa: E741
    total_credit = sum(float(l.credit) for l in entry.lines)  # noqa: E741
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(
            status_code=422,
            detail=f"Tidak seimbang: debit {total_debit} != kredit {total_credit}",
        )
    assert_period_open(db, entry.entry_date)
    for line in entry.lines:
        acc = db.get(Account, line.account_id) if line.account_id else None
        if acc is None or not acc.is_active:
            raise HTTPException(
                status_code=422, detail="Ada baris dengan akun tidak aktif/tidak dikenal"
            )

    entry.status = JournalEntryStatus.posted
    entry.posted_at = datetime.now(UTC)
    db.commit()
    db.refresh(entry)
    return entry


def list_entries(
    db: Session,
    year: int | None = None,
    month: int | None = None,
    status=None,
    event_code: str | None = None,
) -> list[JournalEntry]:
    stmt = select(JournalEntry).order_by(JournalEntry.entry_date.desc())
    if year is not None:
        stmt = stmt.where(func.extract("year", JournalEntry.entry_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", JournalEntry.entry_date) == month)
    if status is not None:
        stmt = stmt.where(JournalEntry.status == status)
    if event_code is not None:
        stmt = stmt.where(JournalEntry.event_code == event_code)
    return list(db.execute(stmt).unique().scalars())


# ---------- Mesin auto-journal (PRD §8.3) ----------


def post_auto_event(
    db: Session,
    *,
    tenant_id,
    event_code: str,
    source_ref_type: str,
    source_ref_id,
    entry_date: date,
    description: str,
    lines: list[tuple[str, float, float]],  # (account_code, debit, credit)
    client_dim_id=None,
    reference: str | None = None,
) -> JournalEntry | None:
    """Idempoten: satu dokumen sumber → tepat satu jurnal per event.

    - Event harus punya rule aktif (journal_rules).
    - Periode tujuan wajib open; bila ditutup → event dilewati (log) agar
      operasi bisnis tidak gagal, konsisten prinsip "input backdate ditolak".
    """
    rule = db.execute(
        select(JournalRule).where(JournalRule.event_code == event_code)
    ).scalar_one_or_none()
    if rule is not None and not rule.is_active:
        return None

    duplicate = db.execute(
        select(JournalEntry).where(
            JournalEntry.event_code == event_code,
            JournalEntry.source_ref_type == source_ref_type,
            JournalEntry.source_ref_id == parse_uuid(source_ref_id),
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        return duplicate

    try:
        assert_period_open(db, entry_date)
    except HTTPException as exc:
        import logging

        logging.getLogger(__name__).warning("Auto-journal %s dilewati: %s", event_code, exc.detail)
        return None

    entry = JournalEntry(
        entry_date=entry_date,
        description=description,
        reference=reference,
        status=JournalEntryStatus.posted,
        posted_at=datetime.now(UTC),
        event_code=event_code,
        source_ref_type=source_ref_type,
        source_ref_id=parse_uuid(source_ref_id),
    )
    for code, debit, credit in lines:
        account = get_account_by_code(db, code)
        entry.lines.append(
            JournalLine(
                account_code=code,
                account_id=account.id if account else None,
                debit=debit,
                credit=credit,
                client_dim_id=client_dim_id,
                memo=(description or "")[:200] or None,
            )
        )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------- Laporan (hanya jurnal posted) ----------


def _posted_totals(
    db: Session, until: str, start: str | None = None
) -> dict[str, tuple[float, float]]:
    """Total debit/kredit per kode akun dari jurnal POSTED."""
    join_cond = [
        JournalLine.entry_id == JournalEntry.id,
        JournalEntry.status == JournalEntryStatus.posted,
        JournalEntry.entry_date <= until,
    ]
    if start is not None:
        join_cond.append(JournalEntry.entry_date >= start)
    effective_code = func.coalesce(Account.code, JournalLine.account_code)
    stmt = (
        select(
            effective_code,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .outerjoin(Account, JournalLine.account_id == Account.id)
        .where(*join_cond)
        .group_by(effective_code)
    )
    totals: dict[str, tuple[float, float]] = {}
    for code, debit, credit in db.execute(stmt).all():
        totals[code] = (float(debit), float(credit))
    return totals


def _coa_maps(
    db: Session,
) -> tuple[dict[str, Any], dict[str, str]]:
    accounts = list_accounts(db, include_inactive=True)
    by_code: dict[str, Any] = {a.code: a for a in accounts}
    group_of = {a.code: a.group_type.value for a in accounts}
    return by_code, group_of


def _ensure_legacy_codes(totals: dict[str, tuple[float, float]], by_code: dict[str, Any]):
    for code in totals:
        by_code.setdefault(code, _LegacyShim(code))


class _LegacyShim:
    """Jembatan untuk baris legacy tanpa padanan COA (tidak seharusnya terjadi)."""

    def __init__(self, code: str):
        self.code = code
        self.name = f"Akun {code}"
        self.group_type = GroupType.aset_lancar
        self.normal_balance = "debit"


def trial_balance(db: Session, year: int) -> list[TrialBalanceRow]:
    end = f"{year}-12-31"
    totals = _posted_totals(db, end)
    by_code, group_of = _coa_maps(db)
    _ensure_legacy_codes(totals, by_code)
    rows = []
    for code in sorted(set(by_code) | set(totals)):
        account = by_code.get(code) or _LegacyShim(code)
        debit, credit = totals.get(code, (0.0, 0.0))
        rows.append(
            TrialBalanceRow(
                account_code=code,
                account_name=account.name,
                category=group_of.get(
                    code,
                    account.group_type.value if hasattr(account, "group_type") else "aset_lancar",
                ),
                total_debit=debit,
                total_credit=credit,
            )
        )
    return rows


def ledger(db: Session, account_code: str, year: int):
    account = get_account_by_code(db, account_code)
    if account is not None:
        name = account.name
        group = account.group_type.value
        normal_debit = account.normal_balance == "debit"
    else:
        # Fallback legacy statik agar endpoint lama tetap hidup.
        from app.modules.accounting.accounts import get_account as legacy_get

        legacy = legacy_get(account_code)
        if legacy is None:
            raise HTTPException(status_code=404, detail="Kode akun tidak dikenal")
        name = legacy.name
        group = legacy.category
        normal_debit = group in ("aset", "beban")

    start = f"{year}-01-01"
    end = f"{year}-12-31"
    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id, isouter=True)
        .where(
            func.coalesce(Account.code, JournalLine.account_code) == account_code,
            JournalEntry.entry_date >= start,
            JournalEntry.entry_date <= end,
            JournalEntry.status == JournalEntryStatus.posted,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.created_at)
    )
    lines = []
    balance = 0.0
    for line, entry in db.execute(stmt).unique().all():
        delta = (
            float(line.debit) - float(line.credit)
            if normal_debit
            else float(line.credit) - float(line.debit)
        )
        balance += delta
        lines.append(
            {
                "entry_id": str(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "description": entry.description,
                "reference": entry.reference,
                "debit": float(line.debit),
                "credit": float(line.credit),
                "balance": round(balance, 2),
            }
        )
    return {"account": account_code, "account_name": name, "year": year, "lines": lines}


def income_statement(
    db: Session, year: int, month: int | None = None, client_dim_id: str | None = None
) -> IncomeStatement:
    end_day = 31 if month is None else monthrange(year, month)[1]
    end = f"{year}-{str(month or 12).zfill(2)}-{end_day:02d}"
    start = f"{year}-01-01" if month is None else f"{year}-{str(month).zfill(2)}-01"
    totals = _posted_totals(db, end, start=start)
    by_code, group_of = _coa_maps(db)
    _ensure_legacy_codes(totals, by_code)

    revenues: list[IncomeStatementRow] = []
    expenses: list[IncomeStatementRow] = []
    for code in sorted(totals):
        group = group_of.get(code)
        if group is None:
            shim = _LegacyShim(code)
            group = shim.group_type.value
        debit, credit = totals[code]
        amount = credit - debit if group in REVENUE_GROUPS else debit - credit
        if round(amount, 2) == 0:
            continue
        row = IncomeStatementRow(
            account_code=code,
            account_name=(by_code[code].name if code in by_code else f"Akun {code}"),
            amount=round(amount, 2),
        )
        if group in REVENUE_GROUPS:
            revenues.append(row)
        elif group in EXPENSE_GROUPS:
            expenses.append(row)
    total_revenue = round(sum(r.amount for r in revenues), 2)
    total_expense = round(sum(r.amount for r in expenses), 2)
    return IncomeStatement(
        year=year,
        revenues=revenues,
        expenses=expenses,
        total_revenue=total_revenue,
        total_expense=total_expense,
        net_income=round(total_revenue - total_expense, 2),
    )


def balance_sheet(db: Session, as_of: str) -> BalanceSheet:
    totals = _posted_totals(db, as_of)
    by_code, group_of = _coa_maps(db)
    _ensure_legacy_codes(totals, by_code)

    def section(groups: tuple[str, ...], sign: str) -> BalanceSheetSection:
        rows = []
        total = 0.0
        for code in sorted(totals):
            group = group_of.get(code)
            if group not in groups:
                continue
            debit, credit = totals[code]
            amount = round(debit - credit, 2) if sign == "debit" else round(credit - debit, 2)
            rows.append(
                IncomeStatementRow(
                    account_code=code,
                    account_name=(by_code[code].name if code in by_code else f"Akun {code}"),
                    amount=amount,
                )
            )
            total += amount
        return BalanceSheetSection(rows=rows, total=round(total, 2))

    assets = section(("aset_lancar", "aset_tetap"), "debit")
    liabilities = section(("liabilitas_pendek", "liabilitas_panjang"), "kredit")
    equity = section(("ekuitas",), "kredit")

    net = 0.0
    for code, (debit, credit) in totals.items():
        group = group_of.get(code)
        if group in REVENUE_GROUPS:
            net += credit - debit
        elif group in EXPENSE_GROUPS:
            net += debit - credit
    net_income = round(net, 2)
    equity.total = round(equity.total + net_income, 2)

    return BalanceSheet(
        as_of=date.fromisoformat(as_of),
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        net_income=net_income,
    )


def profit_by_client(db: Session, year: int, month: int | None = None) -> list[dict]:
    """Laba rugi per kontrak klien dari dimensi baris jurnal (PRD §8.6)."""
    from app.modules.clients.models import Client

    end_day = 31 if month is None else monthrange(year, month)[1]
    start = f"{year}-01-01" if month is None else f"{year}-{str(month).zfill(2)}-01"
    end = f"{year}-{str(month or 12).zfill(2)}-{end_day:02d}"

    stmt = (
        select(
            JournalLine.client_dim_id,
            Client.name,
            Account.group_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .join(Client, JournalLine.client_dim_id == Client.id)
        .where(
            JournalEntry.status == JournalEntryStatus.posted,
            JournalEntry.entry_date >= start,
            JournalEntry.entry_date <= end,
            JournalLine.client_dim_id.is_not(None),
        )
        .group_by(JournalLine.client_dim_id, Client.name, Account.group_type)
    )
    agg: dict[str, dict] = {}
    for _cid, client_name, group, debit, credit in db.execute(stmt).all():
        bucket = agg.setdefault(client_name, {"revenue": 0.0, "expense": 0.0})
        gv = group.value
        if gv in REVENUE_GROUPS:
            bucket["revenue"] += float(credit) - float(debit)
        elif gv in EXPENSE_GROUPS:
            bucket["expense"] += float(debit) - float(credit)
    result = []
    for client_name, b in sorted(agg.items()):
        revenue = round(b["revenue"], 2)
        expense = round(b["expense"], 2)
        result.append(
            {
                "client": client_name,
                "revenue": revenue,
                "expense": expense,
                "margin": round(revenue - expense, 2),
            }
        )
    return result
