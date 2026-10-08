"""Draf email pengingat pembayaran untuk invoice lewat jatuh tempo.

Audit 2026-10-08 Phase 6 ("collection assistant"): AI membantu MENULIS draf,
manusia yang memutuskan & mengirim. Endpoint ini tidak pernah mengirim apa
pun -- hanya mengembalikan teks untuk disalin. Fakta (nomor invoice, nominal,
jatuh tempo) berasal dari database; draf AI ditolak bila tidak memuat nomor
invoice dan nominal yang persis sama (anti-halusinasi angka ke klien).
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.llm import ai_configured, chat_completion
from app.core.money import format_rupiah
from app.modules.finance.models import Invoice
from app.modules.finance.service import RECEIVABLE_STATUSES, _get_invoice

_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]  # fmt: skip


def _tanggal(d: date) -> str:
    return f"{d.day} {_BULAN[d.month - 1]} {d.year}"


def _template(invoice: Invoice, days_overdue: int) -> tuple[str, str]:
    client = invoice.client
    sapaan = f"Bapak/Ibu {client.pic_name}" if client and client.pic_name else "Bapak/Ibu"
    amount = format_rupiah(invoice.total_due)
    period = f"{_BULAN[invoice.month - 1]} {invoice.year}"
    due = _tanggal(invoice.due_date) if invoice.due_date else "-"
    subject = f"Pengingat pembayaran {invoice.invoice_no}"
    body = (
        f"Yth. {sapaan},\n\n"
        f"Melalui email ini kami ingin mengingatkan bahwa invoice {invoice.invoice_no} "
        f"untuk layanan periode {period} sebesar {amount} telah jatuh tempo pada {due} "
        f"({days_overdue} hari yang lalu).\n\n"
        "Apabila pembayaran sudah dilakukan, mohon abaikan email ini dan kami ucapkan "
        "terima kasih. Bila ada kendala atau pertanyaan terkait invoice tersebut, "
        "silakan balas email ini.\n\n"
        "Hormat kami,\nTim Finance"
    )
    return subject, body


def draft_payment_reminder(db: Session, invoice_id: str) -> dict:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status not in RECEIVABLE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Pengingat hanya untuk invoice yang sudah terkirim dan belum dibayar",
        )
    today = date.today()
    days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
    subject, body = _template(invoice, days_overdue)
    result = {
        "invoice_id": str(invoice.id),
        "to": invoice.client.pic_email if invoice.client else None,
        "subject": subject,
        "body": body,
        "days_overdue": days_overdue,
        "source": "template",
    }
    if ai_configured():
        ai = _try_ai_draft(invoice, subject, body, days_overdue)
        if ai is not None:
            result["subject"], result["body"] = ai
            result["source"] = "ai"
    return result


def _try_ai_draft(
    invoice: Invoice, subject: str, template_body: str, days_overdue: int
) -> tuple[str, str] | None:
    amount = format_rupiah(invoice.total_due)
    try:
        out = chat_completion(
            "Anda menulis email pengingat pembayaran B2B dalam Bahasa Indonesia "
            "yang sopan, singkat, dan profesional untuk perusahaan outsourcing. "
            "Sesuaikan nada dengan lama keterlambatan (makin lama, makin tegas "
            "namun tetap sopan). WAJIB memuat nomor invoice dan nominal persis "
            'seperti di data. Balas JSON: {"subject": str, "body": str}.',
            f"Data (jangan ubah angka/nomor):\n"
            f"- Klien: {invoice.client.name if invoice.client else '-'}\n"
            f"- Nomor invoice: {invoice.invoice_no}\n"
            f"- Nominal: {amount}\n"
            f"- Terlambat: {days_overdue} hari\n\n"
            f"Draf dasar:\n{template_body}",
            json_mode=True,
            feature="finance.payment_reminder",
        )
    except Exception:  # noqa: BLE001 - AI opsional, template tetap tersedia
        return None
    if not isinstance(out, dict):
        return None
    ai_subject = str(out.get("subject") or subject).strip()[:200]
    ai_body = str(out.get("body") or "").strip()[:4000]
    # Draf ke klien tidak boleh membawa angka karangan.
    if invoice.invoice_no not in ai_body or amount not in ai_body:
        return None
    return ai_subject, ai_body
