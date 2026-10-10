"""Rekonsiliasi bank cerdas (PRD §8.8 #2) — impor mutasi rekening + matching fuzzy.

Matching 100% deterministik (tanpa LLM): skor gabungan kemiripan nominal,
jarak tanggal, dan token deskripsi terhadap transaksi kas-bank sistem yang
belum terekonsiliasi DAN jurnal terposting lain yang menyentuh akun kas/bank
(pelunasan invoice/bill, eksekusi payment request, aset) -- dulu hanya
BankTransaction, sehingga baris pelunasan invoice selalu "belum cocok" dan
membuat transaksi bank untuknya mengkredit piutang dua kali.
Item tanpa usulan diberi alasan yang bisa dibaca.
"""

import csv
import io
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.accounting.models import (
    Account,
    BankStatementLine,
    BankTransaction,
    JournalEntry,
    JournalEntryStatus,
    StatementLineStatus,
)
from app.modules.accounting.service import REVERSAL_EVENT_CODE

TEMPLATE_HEADER = ["tanggal", "keterangan", "mutasi_masuk", "mutasi_keluar"]

# Bobot skor & ambang usulan (deterministik).
_W_AMOUNT, _W_DATE, _W_DESC = 0.6, 0.25, 0.15
_SUGGEST_THRESHOLD = 0.75


def template_csv() -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(["2026-08-05", "TRANSFER MASUK PT MAJU", 15000000, 0])
    writer.writerow(["2026-08-07", "PEMBAYARAN ATK SUMBER REZEKI", 0, 350000])
    return buffer.getvalue()


def _parse_amount(raw, key: str) -> float:
    value = (raw or "").strip().replace(",", "") or "0"
    try:
        amt = round(float(value))
    except ValueError:
        raise ValueError(f"{key} bukan angka: '{value}'") from None
    if amt < 0:
        raise ValueError(f"{key} negatif")
    return float(amt)


async def import_statement(db: Session, file: UploadFile) -> dict:
    """Impor CSV rekening koran; baris gagal/duplikat dilaporkan, lainnya diproses."""
    from app.core.csv_upload import read_csv_text

    text = await read_csv_text(file)
    sample = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    inserted, duplicates, failed = 0, [], []
    for idx, row in enumerate(reader, start=2):  # baris 1 = header
        try:
            raw_date = (row.get("tanggal") or "").strip()
            if not raw_date:
                raise ValueError("tanggal kosong")
            try:
                tx_date = date.fromisoformat(raw_date)
            except ValueError:
                raise ValueError(f"Tanggal tidak valid: '{raw_date}' (format YYYY-MM-DD)") from None

            amount_in = _parse_amount(row.get("mutasi_masuk"), "mutasi_masuk")
            amount_out = _parse_amount(row.get("mutasi_keluar"), "mutasi_keluar")
            if amount_in == 0 and amount_out == 0:
                raise ValueError("Mutasi masuk dan keluar sama-sama nol")

            description = (row.get("keterangan") or "").strip()[:500] or None

            dup = db.execute(
                select(BankStatementLine).where(
                    BankStatementLine.tx_date == tx_date,
                    BankStatementLine.amount_in == amount_in,
                    BankStatementLine.amount_out == amount_out,
                    BankStatementLine.description == description,
                )
            ).scalar_one_or_none()
            if dup is not None:
                duplicates.append({"row": idx, "detail": f"Baris identik sudah diimpor ({dup.id})"})
                continue

            line = BankStatementLine(
                tx_date=tx_date,
                description=description,
                amount_in=amount_in,
                amount_out=amount_out,
            )
            db.add(line)
            db.flush()
            _suggest_match(db, line)
            inserted += 1
        except (ValueError, TypeError) as exc:
            failed.append({"row": idx, "error": str(exc)})
            continue

    db.commit()
    audit.log_event(
        db,
        action="bank_statement.imported",
        entity_type="bank_statement",
        detail={"inserted": inserted, "failed": len(failed), "duplicates": len(duplicates)},
    )
    return {"inserted": inserted, "duplicates": duplicates, "failed": failed}


def _suggest_match(db: Session, line: BankStatementLine) -> None:
    """Cari kandidat transaksi kas-bank terbaik; simpan usulan bila ≥ ambang."""
    net = float(line.amount_in) - float(line.amount_out)
    candidates = (
        db.execute(
            select(BankTransaction).where(
                BankTransaction.reconciled_at.is_(None),
                # Transaksi yang jurnalnya sudah dibalik bukan mutasi kas nyata.
                _live_tx_filter(),
            )
        )
        .scalars()
        .all()
    )
    best: tuple[float, BankTransaction | JournalEntry | None] = 0.0, None
    best_reason_detail = ""
    pool: list[tuple[BankTransaction | JournalEntry, float, date, str]] = [
        (tx, _signed_amount(tx), tx.tx_date, tx.description or "") for tx in candidates
    ]
    pool += [
        (entry, signed, entry.entry_date, entry.description or "")
        for entry, signed in _cash_journal_candidates(db, line.tx_date)
    ]
    for ref, signed, ref_date, ref_desc in pool:
        amount_score = _amount_score(net, signed)
        if amount_score == 0.0:
            continue
        days = abs((ref_date - line.tx_date).days)
        date_score = max(0.0, 1.0 - days / 14.0) if days <= 14 else 0.0
        desc_score = _desc_similarity(line.description or "", ref_desc)
        total = _W_AMOUNT * amount_score + _W_DATE * date_score + _W_DESC * desc_score
        if total > best[0]:
            best = total, ref
            best_reason_detail = f"{days} hari · deskripsi mirip {desc_score:.0%}"
    line.suggested_tx_id = None
    line.suggested_journal_id = None
    if best[0] >= _SUGGEST_THRESHOLD and best[1] is not None:
        line.status = StatementLineStatus.suggested
        if isinstance(best[1], JournalEntry):
            line.suggested_journal_id = best[1].id
            best_reason_detail += " · jurnal " + (best[1].event_code or "manual")
        else:
            line.suggested_tx_id = best[1].id
        line.match_score = round(best[0], 4)
        line.match_reason = f"Kandidat: {best_reason_detail}"[:500]
    else:
        line.status = StatementLineStatus.unmatched
        line.match_score = round(best[0], 4)
        line.match_reason = _no_match_reason(db, net, line.tx_date)


def _amount_score(statement_net: float, tx_signed: float) -> float:
    diff = abs(statement_net - tx_signed)
    if diff == 0:
        return 1.0
    base = max(abs(statement_net), abs(tx_signed), 1.0)
    ratio = diff / base
    if ratio <= 0.005:  # toleransi biaya admin ≤ 0,5%
        return 0.8
    return 0.0


def _desc_similarity(a: str, b: str) -> float:
    stop = {"transfer", "masuk", "keluar", "trx", "id", "bank", "dr", "cr", "to", "from"}
    ta = {w for w in a.lower().split() if len(w) > 2 and w not in stop}
    tb = {w for w in b.lower().split() if len(w) > 2 and w not in stop}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _signed_amount(tx: BankTransaction) -> float:
    return float(tx.amount) * (-1 if tx.tx_type.value == "pembayaran" else 1)


def _cash_codes(db: Session) -> set[str]:
    return set(db.execute(select(Account.code).where(Account.is_cash_bank.is_(True))).scalars())


def _reversed_journal_ids():
    """Subquery id jurnal yang efektif dibalik.

    Jurnal X dibalik oleh R (`journal_reversed`, `source_ref_id = X`) -- KECUALI
    R sendiri sudah dibalik lagi (membatalkan pembalikan yang keliru), yang
    membuat X berlaku kembali. Cukup satu tingkat; rantai lebih dalam sangat
    jarang dan tidak dimodelkan.
    """
    reversals_of_reversals = select(JournalEntry.source_ref_id).where(
        JournalEntry.event_code == REVERSAL_EVENT_CODE,
        JournalEntry.source_ref_type == "journal_entry",
        JournalEntry.source_ref_id.is_not(None),
    )
    return select(JournalEntry.source_ref_id).where(
        JournalEntry.event_code == REVERSAL_EVENT_CODE,
        JournalEntry.source_ref_type == "journal_entry",
        JournalEntry.source_ref_id.is_not(None),
        JournalEntry.id.not_in(reversals_of_reversals),
    )


def _live_tx_filter():
    """Transaksi kas-bank yang jurnalnya masih berlaku (tidak dibalik)."""
    return or_(
        BankTransaction.journal_entry_id.is_(None),
        BankTransaction.journal_entry_id.not_in(_reversed_journal_ids()),
    )


def _cash_journal_candidates(
    db: Session, around: date, window_days: int = 14
) -> list[tuple[JournalEntry, float]]:
    """Jurnal terposting yang menyentuh kas/bank & belum direkonsiliasi.

    Dikecualikan: jurnal milik BankTransaction (dicocokkan lewat transaksinya,
    supaya satu mutasi tidak punya dua kandidat) dan jurnal yang sudah dipakai
    baris rekening koran lain. Nilai = Σ(debit - kredit) baris kas/bank:
    positif = uang masuk, negatif = keluar.
    """
    cash = _cash_codes(db)
    if not cash:
        return []
    tx_journals = select(BankTransaction.journal_entry_id).where(
        BankTransaction.journal_entry_id.is_not(None)
    )
    used = select(BankStatementLine.matched_journal_id).where(
        BankStatementLine.matched_journal_id.is_not(None)
    )
    reversed_ids = _reversed_journal_ids()
    entries = (
        db.execute(
            select(JournalEntry).where(
                JournalEntry.status == JournalEntryStatus.posted,
                JournalEntry.entry_date >= around - timedelta(days=window_days),
                JournalEntry.entry_date <= around + timedelta(days=window_days),
                JournalEntry.id.not_in(tx_journals),
                JournalEntry.id.not_in(used),
                # Bukan pergerakan uang: jurnal yang sudah dibalik (efek bersih
                # nol) dan jurnal pembaliknya sendiri.
                JournalEntry.id.not_in(reversed_ids),
                or_(
                    JournalEntry.event_code.is_(None),
                    JournalEntry.event_code != REVERSAL_EVENT_CODE,
                ),
            )
        )
        .scalars()
        .all()
    )
    out: list[tuple[JournalEntry, float]] = []
    for entry in entries:
        cash_lines = [ln for ln in entry.lines if ln.account_code in cash]
        if not cash_lines:
            continue
        signed = sum(float(ln.debit) - float(ln.credit) for ln in cash_lines)
        if signed:
            out.append((entry, signed))
    return out


def _no_match_reason(db: Session, net: float, around: date) -> str:
    candidates = (
        db.execute(
            select(BankTransaction).where(
                BankTransaction.reconciled_at.is_(None), _live_tx_filter()
            )
        )
        .scalars()
        .all()
    )
    near = any(_amount_score(net, _signed_amount(tx)) > 0 for tx in candidates) or any(
        _amount_score(net, signed) > 0 for _, signed in _cash_journal_candidates(db, around)
    )
    if not near:
        return "Tidak ada mutasi sistem dengan nominal serupa yang belum terekonsiliasi"
    return "Ada kandidat nominal serupa namun tanggal/deskripsi terlalu jauh (skor di bawah ambang)"


def list_statement_lines(db: Session, status: StatementLineStatus | None = None) -> list[dict]:
    stmt = select(BankStatementLine).order_by(
        BankStatementLine.tx_date.desc(), BankStatementLine.created_at.desc()
    )
    if status is not None:
        stmt = stmt.where(BankStatementLine.status == status)
    lines = list(db.execute(stmt).scalars())
    tx_cache: dict = {}
    result = []
    for ln in lines:
        ref_id = ln.matched_tx_id or ln.suggested_tx_id
        if ref_id and ref_id not in tx_cache:
            tx_cache[ref_id] = db.get(BankTransaction, ref_id)
        ref = tx_cache.get(ref_id)
        journal_id = ln.matched_journal_id or ln.suggested_journal_id
        journal = db.get(JournalEntry, journal_id) if journal_id else None
        result.append(
            {
                "id": str(ln.id),
                "tx_date": ln.tx_date.isoformat(),
                "description": ln.description,
                "amount_in": float(ln.amount_in),
                "amount_out": float(ln.amount_out),
                "status": ln.status.value,
                "match_score": float(ln.match_score),
                "match_reason": ln.match_reason,
                "suggested_tx_id": str(ln.suggested_tx_id) if ln.suggested_tx_id else None,
                "suggested_tx_description": (
                    ref.description if ref else (journal.description if journal else None)
                ),
                "matched_tx_id": str(ln.matched_tx_id) if ln.matched_tx_id else None,
                "suggested_journal_id": (
                    str(ln.suggested_journal_id) if ln.suggested_journal_id else None
                ),
                "matched_journal_id": str(ln.matched_journal_id) if ln.matched_journal_id else None,
            }
        )
    return result


def _clear_stale_suggestions(
    db: Session, line: BankStatementLine, *, tx_id=None, journal_id=None
) -> None:
    """Usulan di baris lain yang menunjuk pasangan yang sama jadi basi."""
    cond = (
        BankStatementLine.suggested_tx_id == tx_id
        if tx_id is not None
        else BankStatementLine.suggested_journal_id == journal_id
    )
    stale = (
        db.execute(
            select(BankStatementLine).where(
                cond,
                BankStatementLine.id != line.id,
                BankStatementLine.status == StatementLineStatus.suggested,
            )
        )
        .scalars()
        .all()
    )
    for other in stale:
        other.status = StatementLineStatus.unmatched
        other.suggested_tx_id = None
        other.suggested_journal_id = None
        other.match_score = 0
        other.match_reason = "Nominal sudah dipakai baris rekening koran lain"


def _open_line(db: Session, line_id: str) -> BankStatementLine:
    line = db.get(BankStatementLine, parse_uuid(line_id))
    if line is None:
        raise HTTPException(status_code=404, detail="Baris statement tidak ditemukan")
    if line.status == StatementLineStatus.matched:
        raise HTTPException(status_code=409, detail="Baris sudah tercocok")
    if line.status == StatementLineStatus.ignored:
        raise HTTPException(status_code=409, detail="Baris diabaikan — batalkan abaikan dahulu")
    return line


def confirm_match(
    db: Session,
    *,
    user,
    line_id: str,
    bank_transaction_id: str | None = None,
    journal_entry_id: str | None = None,
) -> dict:
    """Konfirmasi usulan/pilihan manual → baris cocok + pasangan terekonsiliasi.

    Pasangan = transaksi kas-bank ATAU jurnal terposting yang menyentuh kas/bank
    (tanpa BankTransaction). Tidak ada jurnal baru yang dibuat di sini.
    """
    line = _open_line(db, line_id)
    now = datetime.now(UTC)
    if journal_entry_id:
        entry = db.get(JournalEntry, parse_uuid(journal_entry_id))
        if entry is None or entry.status != JournalEntryStatus.posted:
            raise HTTPException(status_code=404, detail="Jurnal terposting tidak ditemukan")
        if (
            entry.event_code == REVERSAL_EVENT_CODE
            or db.execute(
                _reversed_journal_ids().where(JournalEntry.source_ref_id == entry.id)
            ).first()
        ):
            raise HTTPException(
                status_code=422,
                detail="Jurnal ini sudah dibalik (atau jurnal pembalik) -- bukan mutasi kas nyata",
            )
        if db.execute(
            select(BankTransaction.id).where(BankTransaction.journal_entry_id == entry.id)
        ).first():
            raise HTTPException(
                status_code=422,
                detail="Jurnal ini milik transaksi kas-bank — cocokkan lewat transaksinya",
            )
        if db.execute(
            select(BankStatementLine.id).where(BankStatementLine.matched_journal_id == entry.id)
        ).first():
            raise HTTPException(status_code=409, detail="Jurnal sudah terekonsiliasi")
        cash = _cash_codes(db)
        if not any(ln.account_code in cash for ln in entry.lines):
            raise HTTPException(status_code=422, detail="Jurnal tidak menyentuh akun kas/bank")
        line.matched_journal_id = entry.id
        line.match_reason = f"Tercocok ke jurnal: {entry.description}"[:500]
        detail = {"journal_entry": str(entry.id)}
        _clear_stale_suggestions(db, line, journal_id=entry.id)
    else:
        tx = db.get(BankTransaction, parse_uuid(str(bank_transaction_id or "")))
        if tx is None:
            raise HTTPException(status_code=404, detail="Transaksi kas-bank tidak ditemukan")
        if tx.reconciled_at is not None:
            raise HTTPException(status_code=409, detail="Transaksi sudah terekonsiliasi")
        line.matched_tx_id = tx.id
        line.match_reason = f"Tercocok ke transaksi: {tx.description or tx.tx_type.value}"[:500]
        tx.reconciled_at = now
        detail = {"bank_transaction": str(tx.id)}
        _clear_stale_suggestions(db, line, tx_id=tx.id)

    line.status = StatementLineStatus.matched
    line.confirmed_by_id = user.id
    line.confirmed_at = now
    db.commit()
    audit.log_event(
        db,
        action="bank_statement.matched",
        entity_type="bank_statement_line",
        entity_id=line.id,
        detail={**detail, "by": getattr(user, "email", "?")},
    )
    return {"id": str(line.id), "status": line.status.value}


def ignore_line(db: Session, *, user, line_id: str) -> dict:
    line = db.get(BankStatementLine, parse_uuid(line_id))
    if line is None:
        raise HTTPException(status_code=404, detail="Baris statement tidak ditemukan")
    if line.status == StatementLineStatus.matched:
        raise HTTPException(status_code=409, detail="Baris sudah tercocok — tidak bisa diabaikan")
    line.status = StatementLineStatus.ignored
    line.suggested_tx_id = None
    line.match_reason = "Diabaikan manual"
    db.commit()
    audit.log_event(
        db,
        action="bank_statement.ignored",
        entity_type="bank_statement_line",
        entity_id=line.id,
        detail={"by": getattr(user, "email", "?")},
    )
    return {"id": str(line.id), "status": line.status.value}


# ---------- Saran untuk baris tanpa pasangan (peluang AI #6) ----------
#
# Semua saran deterministik dan TIDAK pernah memposting apa pun sendiri:
# user memilih satu aksi, aksi memanggil alur bisnis yang sudah ada (tandai
# lunas invoice, bayar bill, transaksi kas-bank) lalu baris langsung
# dicocokkan ke jurnal hasilnya.

# Kata kunci keterangan mutasi -> akun lawan (kode bagan akun bawaan).
_KEYWORD_ACCOUNTS: list[tuple[tuple[str, ...], str, str]] = [
    # (kata kunci, arah "masuk"/"keluar", kode akun)
    # Urutan: frasa terpanjang dulu, supaya alasan menyebut kata yang paling spesifik.
    (("biaya admin", "biaya adm", "adm bank", "biaya transfer", "provisi"), "keluar", "5-9000"),
    (("bunga", "jasa giro"), "masuk", "4-9000"),
    (("bunga",), "keluar", "6-1000"),
]
_HISTORY_MIN_SIMILARITY = 0.5


def _net(line: BankStatementLine) -> float:
    return float(line.amount_in) - float(line.amount_out)


def suggest_actions(db: Session, line_id: str) -> dict:
    from app.modules.accounting.models import BillStatus, PurchaseBill
    from app.modules.finance.models import Invoice
    from app.modules.finance.service import RECEIVABLE_STATUSES

    line = _open_line(db, line_id)
    net = _net(line)
    amount = round(abs(net))
    desc = (line.description or "").lower()
    actions: list[dict] = []

    if net > 0:
        invoices = db.execute(
            select(Invoice).where(Invoice.status.in_(RECEIVABLE_STATUSES))
        ).scalars()
        for inv in invoices:
            if round(float(inv.total_due)) == amount:
                actions.append(
                    {
                        "kind": "settle_invoice",
                        "label": f"Tandai lunas invoice {inv.invoice_no}",
                        "reason": "Nominal sama persis dengan piutang terbuka",
                        "invoice_id": str(inv.id),
                    }
                )
    elif net < 0:
        bills = db.execute(
            select(PurchaseBill).where(PurchaseBill.status == BillStatus.unpaid)
        ).scalars()
        for bill in bills:
            if round(float(bill.amount) + float(bill.ppn_amount)) == amount:
                actions.append(
                    {
                        "kind": "pay_bill",
                        "label": f"Bayar bill {bill.vendor_name}",
                        "reason": "Nominal sama persis dengan bill belum dibayar",
                        "bill_id": str(bill.id),
                    }
                )

    # Akun lawan dari riwayat: baris serupa yang sudah dicocokkan ke transaksi
    # kas-bank dengan akun lawan.
    seen_accounts: set = set()
    matched = db.execute(
        select(BankStatementLine, BankTransaction)
        .join(BankTransaction, BankTransaction.id == BankStatementLine.matched_tx_id)
        .where(
            BankStatementLine.status == StatementLineStatus.matched,
            BankTransaction.counter_account_id.is_not(None),
        )
        .order_by(BankStatementLine.tx_date.desc())
    ).all()
    for past, tx in matched:
        if (_net(past) > 0) != (net > 0) or tx.counter_account_id in seen_accounts:
            continue
        sim = _desc_similarity(line.description or "", past.description or "")
        if sim < _HISTORY_MIN_SIMILARITY:
            continue
        account = db.get(Account, tx.counter_account_id)
        if account is None:
            continue
        seen_accounts.add(account.id)
        actions.append(
            {
                "kind": "create_transaction",
                "label": f"Catat ke {account.code} {account.name}",
                "reason": f'Mirip mutasi {past.tx_date.isoformat()} "{past.description}"',
                "counter_account_id": str(account.id),
            }
        )

    direction = "masuk" if net > 0 else "keluar"
    for keywords, kw_direction, code in _KEYWORD_ACCOUNTS:
        if kw_direction != direction or not any(k in desc for k in keywords):
            continue
        account = db.execute(select(Account).where(Account.code == code)).scalar_one_or_none()
        if account is None or account.id in seen_accounts:
            continue
        seen_accounts.add(account.id)
        hit = next(k for k in keywords if k in desc)
        actions.append(
            {
                "kind": "create_transaction",
                "label": f"Catat ke {account.code} {account.name}",
                "reason": f'Keterangan memuat "{hit}"',
                "counter_account_id": str(account.id),
            }
        )

    bank_accounts = db.execute(
        select(Account).where(Account.is_cash_bank.is_(True)).order_by(Account.code)
    ).scalars()
    return {
        "line_id": str(line.id),
        "direction": direction,
        "amount": amount,
        "actions": actions,
        # Rekening koran tidak menyimpan rekeningnya: user memilih akun bank
        # untuk aksi bayar bill / transaksi baru.
        "bank_accounts": [{"id": str(a.id), "code": a.code, "name": a.name} for a in bank_accounts],
    }


def apply_action(db: Session, *, user, line_id: str, payload: dict) -> dict:
    """Jalankan satu saran lalu cocokkan baris ke jurnal/transaksi hasilnya."""
    from app.modules.accounting import transactions_service
    from app.modules.accounting.models import PurchaseBill
    from app.modules.finance.service import mark_invoice_paid_from_bank

    line = _open_line(db, line_id)
    net = _net(line)
    kind = payload.get("kind")
    if kind == "settle_invoice":
        if net <= 0:
            raise HTTPException(status_code=422, detail="Pelunasan invoice harus mutasi masuk")
        from app.modules.finance.service import get_invoice

        invoice = get_invoice(db, str(payload.get("invoice_id") or ""))
        if round(float(invoice.total_due)) != round(net):
            raise HTTPException(status_code=422, detail="Nominal invoice tidak sama dengan mutasi")
        invoice, entry = mark_invoice_paid_from_bank(db, str(invoice.id), line.tx_date)
        db.commit()
        if entry is None:
            return {"id": str(line.id), "status": line.status.value, "warning": "jurnal_gagal"}
        return confirm_match(db, user=user, line_id=line_id, journal_entry_id=str(entry.id))

    if kind == "pay_bill":
        if net >= 0:
            raise HTTPException(status_code=422, detail="Pembayaran bill harus mutasi keluar")
        bill = db.get(PurchaseBill, parse_uuid(str(payload.get("bill_id") or "")))
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill tidak ditemukan")
        if round(float(bill.amount) + float(bill.ppn_amount)) != round(-net):
            raise HTTPException(status_code=422, detail="Nominal bill tidak sama dengan mutasi")
        bill = transactions_service.pay_purchase_bill(
            db,
            bill_id=str(bill.id),
            bank_account_id=payload.get("bank_account_id"),
            paid_date=line.tx_date,
        )
        if bill.paid_journal_id is None:
            return {"id": str(line.id), "status": line.status.value, "warning": "jurnal_gagal"}
        return confirm_match(
            db, user=user, line_id=line_id, journal_entry_id=str(bill.paid_journal_id)
        )

    if kind == "create_transaction":
        tx = transactions_service.create_bank_transaction(
            db,
            tx_type="penerimaan" if net > 0 else "pembayaran",
            bank_account_id=payload.get("bank_account_id"),
            amount=abs(net),
            tx_date=line.tx_date,
            counter_account_id=payload.get("counter_account_id"),
            description=line.description,
        )
        return confirm_match(db, user=user, line_id=line_id, bank_transaction_id=str(tx.id))

    raise HTTPException(status_code=422, detail="Aksi tidak dikenal")
