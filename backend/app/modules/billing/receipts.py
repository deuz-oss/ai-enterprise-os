"""Kwitansi resmi Aeos sebagai penjual SaaS (Fase 28 lanjutan, PRD §4.4.5).

Terpisah dari e-Faktur klien (modul finance). Aturan:
- Dibuat SEKALI di transaksi yang sama dengan efek pembayaran -- nomor dan
  snapshot (penjual, pembeli, rincian) dikunci saat itu.
- Nomor `AEOS/KW/{YYYY}/{seq:06d}` berurutan per tahun kalender (Asia/Jakarta)
  LINTAS semua tenant (penjualnya satu). Alokasi atomik lewat
  `UPDATE ... RETURNING` di tabel platform `billing_receipt_sequences` --
  bukan `count()+1` yang rawan race.
- PDF dirender deterministik dari snapshot saat pertama diminta, disimpan ke
  storage, lalu tidak pernah diubah (`pdf_object_key` compare-and-set).
- PPN hanya bila `AEOS_SELLER_IS_PKP=true` + `BILLING_PPN_RATE`; harga
  diperlakukan sudah termasuk PPN supaya total kwitansi == uang diterima.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.money import format_rupiah, round_rupiah, to_decimal
from app.modules.billing.models import (
    BillingReceipt,
    PaymentCharge,
    PaymentIntent,
    ReceiptSource,
    TenantBillingProfile,
)
from app.modules.billing.service import audit_add

logger = logging.getLogger(__name__)

_JAKARTA = ZoneInfo("Asia/Jakarta")


def allocate_receipt_number(db: Session, year: int) -> int:
    """Nomor urut berikutnya untuk `year`, atomik di SQLite (>=3.35) dan
    PostgreSQL. Ikut transaksi pemanggil: rollback = nomor ikut batal,
    tidak ada lubang."""
    db.execute(
        text(
            "INSERT INTO billing_receipt_sequences (year, last_number) VALUES (:y, 0) "
            "ON CONFLICT (year) DO NOTHING"
        ),
        {"y": year},
    )
    value = db.execute(
        text(
            "UPDATE billing_receipt_sequences SET last_number = last_number + 1 "
            "WHERE year = :y RETURNING last_number"
        ),
        {"y": year},
    ).scalar_one()
    return int(value)


def seller_snapshot() -> dict | None:
    """Identitas penjual dari env. None bila belum dikonfigurasi di produksi
    (kwitansi tetap bernomor, render PDF ditunda sampai env diisi -- K8).
    Di luar produksi dipakai placeholder supaya dev/test tetap jalan."""
    settings = get_settings()
    if settings.aeos_seller_name and settings.aeos_seller_npwp:
        return {
            "name": settings.aeos_seller_name,
            "npwp": settings.aeos_seller_npwp,
            "address": settings.aeos_seller_address,
            "email": settings.aeos_seller_email,
            "is_pkp": settings.aeos_seller_is_pkp,
        }
    if settings.app_env == "production":
        return None
    return {
        "name": settings.aeos_seller_name or "Aeos (identitas penjual belum dikonfigurasi)",
        "npwp": settings.aeos_seller_npwp or "-",
        "address": settings.aeos_seller_address,
        "email": settings.aeos_seller_email,
        "is_pkp": settings.aeos_seller_is_pkp,
    }


def buyer_snapshot(db: Session, tenant_id: UUID) -> dict:
    from app.modules.platform.models import Tenant

    profile = db.execute(
        select(TenantBillingProfile).where(TenantBillingProfile.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if profile is not None:
        return {
            "name": profile.legal_name,
            "npwp": profile.npwp,
            "address": profile.address,
            "email": profile.billing_email,
        }
    tenant = db.get(Tenant, tenant_id)
    return {"name": tenant.name if tenant else "-", "npwp": None, "address": None, "email": None}


def _tax_breakdown(total: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """(dpp, tarif, ppn). Non-PKP (default K5) -> tanpa PPN."""
    settings = get_settings()
    rate = settings.billing_ppn_rate
    if not settings.aeos_seller_is_pkp or not rate:
        return total, Decimal(0), Decimal(0)
    dpp = round_rupiah(total / (Decimal(1) + rate))
    return dpp, rate, total - dpp


def issue_receipt(
    db: Session,
    *,
    tenant_id: UUID,
    lines: list[dict],
    total: Decimal,
    payment_method_label: str,
    provider_reference: str | None,
    issued_at: datetime,
    intent: PaymentIntent | None = None,
    charge: PaymentCharge | None = None,
) -> BillingReceipt:
    """Terbitkan kwitansi untuk satu pembayaran berhasil (tanpa commit).
    Idempoten per pembayaran: kwitansi yang sudah ada dikembalikan apa adanya."""
    if intent is not None:
        existing = db.execute(
            select(BillingReceipt).where(BillingReceipt.payment_intent_id == intent.id)
        ).scalar_one_or_none()
    else:
        assert charge is not None
        existing = db.execute(
            select(BillingReceipt).where(BillingReceipt.payment_charge_id == charge.id)
        ).scalar_one_or_none()
    if existing is not None:
        return existing

    local = issued_at.astimezone(_JAKARTA)
    year = local.year
    seq = allocate_receipt_number(db, year)
    total = round_rupiah(total)
    dpp, rate, ppn = _tax_breakdown(total)
    seller = seller_snapshot()
    receipt = BillingReceipt(
        tenant_id=tenant_id,
        receipt_number=f"AEOS/KW/{year}/{seq:06d}",
        receipt_year=year,
        sequence_no=seq,
        source_type=ReceiptSource.payment_intent if intent else ReceiptSource.payment_charge,
        payment_intent_id=intent.id if intent else None,
        payment_charge_id=charge.id if charge else None,
        issued_at=issued_at,
        seller_snapshot_json=json.dumps(seller, ensure_ascii=False) if seller else None,
        buyer_snapshot_json=json.dumps(buyer_snapshot(db, tenant_id), ensure_ascii=False),
        lines_json=json.dumps(lines, ensure_ascii=False, default=str),
        subtotal=total,
        dpp=dpp,
        ppn_rate=rate,
        ppn_amount=ppn,
        total=total,
        payment_method_label=payment_method_label[:80],
        provider_reference=provider_reference,
    )
    db.add(receipt)
    db.flush()
    audit_add(
        db,
        action="billing.receipt_issued",
        entity_type="billing_receipt",
        entity_id=receipt.id,
        detail={"receipt_number": receipt.receipt_number, "total": str(total)},
        tenant_id=tenant_id,
    )
    if seller is None:
        logger.warning(
            "Kwitansi %s terbit tanpa identitas penjual -- set AEOS_SELLER_NAME/NPWP",
            receipt.receipt_number,
        )
    return receipt


def list_receipts(db: Session, tenant_id: UUID, *, limit: int, offset: int) -> list[dict]:
    rows = db.execute(
        select(BillingReceipt)
        .where(BillingReceipt.tenant_id == tenant_id)
        .order_by(BillingReceipt.issued_at.desc(), BillingReceipt.sequence_no.desc())
        .limit(limit)
        .offset(offset)
    ).scalars()
    result = []
    for r in rows:
        lines = json.loads(r.lines_json or "[]")
        result.append(
            {
                "id": str(r.id),
                "receipt_number": r.receipt_number,
                "issued_at": r.issued_at,
                "total": float(r.total),
                "description": lines[0]["description"] if lines else "",
                "source_type": r.source_type.value,
                "payment_method_label": r.payment_method_label,
            }
        )
    return result


def _render_pdf(receipt: BillingReceipt, seller: dict) -> bytes:
    """Render kwitansi (reportlab, idiom sama `presales/rendering.py`):
    import lazy, BytesIO, escape semua teks."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buyer = json.loads(receipt.buyer_snapshot_json)
    lines = json.loads(receipt.lines_json)

    def esc(value: object) -> str:
        return escape(str(value)) if value not in (None, "") else "-"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Kwitansi {receipt.receipt_number}",
        # Metadata tetap supaya PDF deterministik dari snapshot.
        creator="Aeos",
        author="Aeos",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RcTitle", parent=styles["Title"], fontSize=18, spaceAfter=2)
    small = ParagraphStyle("RcSmall", parent=styles["Normal"], fontSize=8.5)
    normal = ParagraphStyle("RcNormal", parent=styles["Normal"], fontSize=10)

    issued_local = receipt.issued_at
    if issued_local.tzinfo is not None:
        issued_local = issued_local.astimezone(_JAKARTA)
    story: list = [
        Paragraph("KWITANSI", title_style),
        Paragraph(
            f"No. {esc(receipt.receipt_number)} &#183; Tanggal {issued_local.strftime('%d/%m/%Y')}",
            normal,
        ),
        Spacer(1, 6 * mm),
    ]
    parties = Table(
        [
            [Paragraph("<b>Penjual</b>", normal), Paragraph("<b>Diterima dari</b>", normal)],
            [Paragraph(esc(seller.get("name")), normal), Paragraph(esc(buyer.get("name")), normal)],
            [
                Paragraph(f"NPWP: {esc(seller.get('npwp'))}", small),
                Paragraph(f"NPWP: {esc(buyer.get('npwp'))}", small),
            ],
            [
                Paragraph(esc(seller.get("address")), small),
                Paragraph(esc(buyer.get("address")), small),
            ],
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [parties, Spacer(1, 6 * mm)]

    data = [["Keterangan", "Qty", "Harga", "Jumlah"]]
    for line in lines:
        data.append(
            [
                Paragraph(esc(line.get("description")), normal),
                str(line.get("qty", 1)),
                format_rupiah(to_decimal(line.get("unit_price"))),
                format_rupiah(to_decimal(line.get("amount"))),
            ]
        )
    data.append(["", "", "Subtotal", format_rupiah(receipt.subtotal)])
    if receipt.ppn_amount and receipt.ppn_amount > 0:
        data.append(["", "", "DPP", format_rupiah(receipt.dpp)])
        pct = (to_decimal(receipt.ppn_rate) * 100).normalize()
        data.append(["", "", f"PPN {pct}%", format_rupiah(receipt.ppn_amount)])
    data.append(["", "", "TOTAL", format_rupiah(receipt.total)])
    table = Table(data, colWidths=[95 * mm, 15 * mm, 32 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story += [table, Spacer(1, 6 * mm)]
    story.append(Paragraph(f"Dibayar dengan: {esc(receipt.payment_method_label)}", small))
    if receipt.provider_reference:
        story.append(Paragraph(f"Referensi gateway: {esc(receipt.provider_reference)}", small))
    if seller.get("is_pkp"):
        story.append(Paragraph("Kwitansi ini bukan Faktur Pajak.", small))
    if receipt.total > Decimal("5000000"):
        story.append(
            Paragraph(
                "Bea meterai atas kwitansi bernilai di atas Rp5.000.000 diselesaikan "
                "terpisah sesuai UU No. 10 Tahun 2020.",
                small,
            )
        )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Dokumen ini diterbitkan secara elektronik oleh sistem Aeos.", small))
    doc.build(story)
    return buffer.getvalue()


def get_receipt_pdf(db: Session, receipt_id: UUID) -> tuple[bytes, str]:
    """Kembalikan (bytes, nama file). Render pertama menyimpan objek dan
    mengunci `pdf_object_key` (compare-and-set); request berikutnya selalu
    menyajikan objek tersimpan -- immutable."""
    from app.core import storage

    receipt = db.get(BillingReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    filename = receipt.receipt_number.replace("/", "-") + ".pdf"
    if receipt.pdf_object_key:
        return storage.get_object(receipt.pdf_object_key), filename

    seller_json = receipt.seller_snapshot_json
    if seller_json is None:
        seller = seller_snapshot()
        if seller is None:
            raise HTTPException(
                status_code=409,
                detail="Identitas penjual belum dikonfigurasi -- kwitansi belum bisa diunduh",
            )
        seller_json = json.dumps(seller, ensure_ascii=False)
    pdf = _render_pdf(receipt, json.loads(seller_json))
    key = f"billing/receipts/{receipt.tenant_id}/{filename}"
    storage.put_object(key, pdf, "application/pdf")
    digest = hashlib.sha256(pdf).hexdigest()
    result = db.execute(
        update(BillingReceipt)
        .where(BillingReceipt.id == receipt.id, BillingReceipt.pdf_object_key.is_(None))
        .values(pdf_object_key=key, pdf_sha256=digest, seller_snapshot_json=seller_json)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if getattr(result, "rowcount", 1) == 0:
        # Request paralel lain sudah mengunci lebih dulu -- sajikan miliknya.
        db.refresh(receipt)
        if receipt.pdf_object_key:
            return storage.get_object(receipt.pdf_object_key), filename
    return pdf, filename
