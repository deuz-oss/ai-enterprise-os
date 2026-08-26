"""Rekonsiliasi bank cerdas (PRD §8.8 #2) — impor mutasi rekening + matching fuzzy.

Matching 100% deterministik (tanpa LLM): skor gabungan kemiripan nominal,
jarak tanggal, dan token deskripsi terhadap transaksi kas-bank sistem yang
belum terekonsiliasi. Item tanpa usulan diberi alasan yang bisa dibaca.
"""

import csv
import io
from datetime import UTC, date, datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.accounting.models import (
    BankStatementLine,
    BankTransaction,
    StatementLineStatus,
)

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
    raw = await file.read()
    text = raw.decode("utf-8-sig")
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
            )
        )
        .scalars()
        .all()
    )
    best: tuple[float, BankTransaction | None] = 0.0, None
    best_reason_detail = ""
    for tx in candidates:
        signed = _signed_amount(tx)
        amount_score = _amount_score(net, signed)
        if amount_score == 0.0:
            continue
        days = abs((tx.tx_date - line.tx_date).days)
        date_score = max(0.0, 1.0 - days / 14.0) if days <= 14 else 0.0
        desc_score = _desc_similarity(line.description or "", tx.description or "")
        total = _W_AMOUNT * amount_score + _W_DATE * date_score + _W_DESC * desc_score
        if total > best[0]:
            best = total, tx
            best_reason_detail = f"{days} hari · deskripsi mirip {desc_score:.0%}"
    if best[0] >= _SUGGEST_THRESHOLD and best[1] is not None:
        line.status = StatementLineStatus.suggested
        line.suggested_tx_id = best[1].id
        line.match_score = round(best[0], 4)
        line.match_reason = f"Kandidat: {best_reason_detail}"[:500]
    else:
        line.status = StatementLineStatus.unmatched
        line.match_score = round(best[0], 4)
        line.match_reason = _no_match_reason(db, net)


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


def _no_match_reason(db: Session, net: float) -> str:
    candidates = (
        db.execute(select(BankTransaction).where(BankTransaction.reconciled_at.is_(None)))
        .scalars()
        .all()
    )
    near = [tx for tx in candidates if _amount_score(net, _signed_amount(tx)) > 0]
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
                "suggested_tx_description": ref.description if ref else None,
                "matched_tx_id": str(ln.matched_tx_id) if ln.matched_tx_id else None,
            }
        )
    return result


def confirm_match(db: Session, *, user, line_id: str, bank_transaction_id: str) -> dict:
    """Konfirmasi usulan/pilihan manual → baris cocok + transaksi terekonsiliasi."""
    line = db.get(BankStatementLine, parse_uuid(line_id))
    if line is None:
        raise HTTPException(status_code=404, detail="Baris statement tidak ditemukan")
    if line.status == StatementLineStatus.matched:
        raise HTTPException(status_code=409, detail="Baris sudah tercocok")
    if line.status == StatementLineStatus.ignored:
        raise HTTPException(status_code=409, detail="Baris diabaikan — batalkan abaikan dahulu")
    tx = db.get(BankTransaction, parse_uuid(bank_transaction_id))
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaksi kas-bank tidak ditemukan")
    if tx.reconciled_at is not None:
        raise HTTPException(status_code=409, detail="Transaksi sudah terekonsiliasi")

    now = datetime.now(UTC)
    line.status = StatementLineStatus.matched
    line.matched_tx_id = tx.id
    line.confirmed_by_id = user.id
    line.confirmed_at = now
    tx.reconciled_at = now

    # Bersihkan usulan basi di baris lain yang menunjuk transaksi yang sama.
    stale = (
        db.execute(
            select(BankStatementLine).where(
                BankStatementLine.suggested_tx_id == tx.id,
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
        other.match_score = 0
        other.match_reason = "Nominal sudah dipakai baris rekening koran lain"

    db.commit()
    audit.log_event(
        db,
        action="bank_statement.matched",
        entity_type="bank_statement_line",
        entity_id=line.id,
        detail={"bank_transaction": str(tx.id), "by": getattr(user, "email", "?")},
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
