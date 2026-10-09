"""Pengaman harga quotation (peluang AI #7 audit 2026-10-08).

Template quotation berisi field bebas; admin menandai field tertentu dengan
`role` (lihat `PRICING_ROLES`) supaya sistem tahu mana gaji, fee, dan harga.
Dari situ dihitung biaya per orang per bulan -- gaji pokok + tunjangan +
iuran BPJS perusahaan (engine BPJS & tarif ber-versi dari Rates, sama dengan
payroll) -- lalu dibandingkan dengan harga tagih. Semua deterministik; tidak
ada AI dan tidak ada yang diubah/diblokir: hasilnya peringatan untuk pembuat
dan approver quotation.

Asumsi (ditampilkan juga di UI):
- `management_fee_pct` dihitung dari total biaya tenaga kerja (gaji +
  tunjangan + BPJS perusahaan), dalam satuan persen ("10" = 10%).
- PPN dan PPh 23 tidak masuk margin (pajak, bukan pendapatan).
- BPJS memakai kelas risiko JKK default konfigurasi Rates.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import ZERO, format_rupiah, round_rupiah, to_decimal
from app.modules.presales.models import Quotation, QuotationTemplate

PRICING_ROLES = {
    "base_salary": "Gaji pokok per orang",
    "allowance": "Tunjangan tetap per orang",
    "management_fee_pct": "Management fee (%)",
    "management_fee_amount": "Management fee per orang (Rp)",
    "price_per_head": "Harga tagih per orang per bulan",
    "headcount": "Jumlah orang",
}

# Margin di bawah ini (terhadap harga) diberi peringatan.
MIN_MARGIN_PCT = Decimal("0.05")
# Fee turun sebanyak ini (relatif) dibanding quotation sebelumnya ke lead sama.
FEE_DROP_RATIO = Decimal("0.25")

_NUM_CLEAN = re.compile(r"[^\d.,\-]")


def parse_number(value: object) -> Decimal | None:
    """Angka dari isian quotation: 5000000, "5.000.000", "Rp 5.000.000,50", "10%".

    Titik dianggap pemisah ribuan bila diikuti kelompok 3 digit (format
    Indonesia); koma = desimal. Tidak terbaca -> None (bukan 0, supaya tidak
    diam-diam menghasilkan margin palsu).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return to_decimal(value)
    text = _NUM_CLEAN.sub("", str(value)).strip()
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _num_id(value: Decimal) -> str:
    """Angka format Indonesia untuk pesan: 2.5 -> "2,5", 12.0 -> "12"."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _pct_id(ratio: Decimal) -> str:
    return f"{_num_id(ratio * 100)}%"


def _roles(template: QuotationTemplate) -> dict[str, str]:
    """role -> key field pada template."""
    out: dict[str, str] = {}
    for f in json.loads(template.field_schema or "[]"):
        role = f.get("role")
        if role in PRICING_ROLES and role not in out:
            out[role] = f["key"]
    return out


def _fee_pct_history(
    db: Session, lead_id: object, template: QuotationTemplate, current: Quotation | None
) -> list[Decimal]:
    """Fee % quotation lain ke lead yang sama (template sama), terlama dulu.

    Untuk quotation tersimpan hanya yang dibuat sebelum quotation itu."""
    roles = _roles(template)
    key = roles.get("management_fee_pct")
    if key is None or lead_id is None:
        return []
    rows = db.execute(
        select(Quotation)
        .where(Quotation.lead_id == lead_id, Quotation.template_id == template.id)
        .order_by(Quotation.created_at)
    ).scalars()
    history: list[Decimal] = []
    for q in rows:
        if current is not None and (
            q.id == current.id
            # Ketat (>): timestamp beresolusi detik, quotation yang dibuat di
            # detik yang sama tetap dihitung sebagai riwayat.
            or (q.created_at and current.created_at and q.created_at > current.created_at)
        ):
            continue
        pct = parse_number(json.loads(q.field_values or "{}").get(key))
        if pct is not None:
            history.append(pct)
    return history


def check_pricing(
    db: Session,
    template: QuotationTemplate,
    field_values: dict,
    *,
    lead_id: object = None,
    current: Quotation | None = None,
    on_date: date | None = None,
) -> dict:
    roles = _roles(template)
    findings: list[dict] = []

    def add(severity: str, kind: str, message: str) -> None:
        findings.append({"severity": severity, "kind": kind, "message": message})

    values: dict[str, Decimal | None] = {}
    for role, key in roles.items():
        raw = field_values.get(key)
        if raw in (None, ""):
            values[role] = None
            continue
        parsed = parse_number(raw)
        values[role] = parsed
        if parsed is None:
            add("medium", "tidak_terbaca", f'{PRICING_ROLES[role]}: nilai "{raw}" tidak terbaca.')

    has_price_role = any(
        r in roles for r in ("price_per_head", "management_fee_pct", "management_fee_amount")
    )
    result: dict = {
        "applicable": "base_salary" in roles and has_price_role,
        "roles": {role: roles[role] for role in roles},
        "per_head": None,
        "monthly": None,
        "history": None,
        "min_margin_pct": float(MIN_MARGIN_PCT),
        "findings": findings,
    }
    if not result["applicable"]:
        return result

    base = values.get("base_salary")
    if base is None:
        return result  # belum diisi: belum ada yang bisa dinilai

    from app.modules.bpjs.engine import compute_contribution

    allowance = values.get("allowance") or ZERO
    bpjs = compute_contribution(base, db=db, effective_date=on_date or date.today())
    bpjs_employer = to_decimal(bpjs.employer_total)
    cost = round_rupiah(base + allowance + bpjs_employer)

    fee_pct = values.get("management_fee_pct")
    fee_amount = values.get("management_fee_amount")
    if fee_amount is None and fee_pct is not None:
        fee_amount = round_rupiah(cost * fee_pct / Decimal(100))
    price = values.get("price_per_head")
    if price is None:
        if fee_amount is None:
            return result  # fee/harga belum diisi
        price = cost + fee_amount
    price = round_rupiah(price)
    margin = price - cost
    margin_pct = (margin / price) if price else None

    result["per_head"] = {
        "base_salary": float(base),
        "allowance": float(allowance),
        "bpjs_employer": float(bpjs_employer),
        "cost": float(cost),
        "fee": float(fee_amount) if fee_amount is not None else None,
        "price": float(price),
        "margin": float(margin),
        "margin_pct": float(margin_pct) if margin_pct is not None else None,
    }
    headcount = values.get("headcount")
    if headcount is not None and headcount > 0:
        result["monthly"] = {
            "headcount": int(headcount),
            "price": float(price * headcount),
            "cost": float(cost * headcount),
            "margin": float(margin * headcount),
        }

    if margin < 0:
        add(
            "high",
            "rugi",
            f"Harga {format_rupiah(price)} di bawah biaya {format_rupiah(cost)} per orang "
            f"(rugi {format_rupiah(-margin)}/orang/bulan).",
        )
    elif margin_pct is not None and margin_pct < MIN_MARGIN_PCT:
        add(
            "medium",
            "margin_tipis",
            f"Margin {_pct_id(margin_pct)} di bawah batas {_pct_id(MIN_MARGIN_PCT)} "
            f"({format_rupiah(margin)}/orang/bulan).",
        )
    if price is not None and values.get("price_per_head") is not None and fee_amount is not None:
        implied = cost + fee_amount
        if abs(implied - price) > Decimal(1):
            add(
                "medium",
                "harga_tidak_konsisten",
                f"Harga per orang {format_rupiah(price)} berbeda dari biaya + fee "
                f"{format_rupiah(implied)}.",
            )

    history = _fee_pct_history(db, lead_id, template, current)
    if history:
        result["history"] = {
            "count": len(history),
            "last_fee_pct": float(history[-1]),
            "median_fee_pct": float(median(history)),
        }
        last = history[-1]
        if fee_pct is not None and last > 0 and (last - fee_pct) / last >= FEE_DROP_RATIO:
            add(
                "medium",
                "fee_turun",
                f"Fee {_num_id(fee_pct)}% jauh di bawah quotation sebelumnya ke lead ini "
                f"({_num_id(last)}%).",
            )

    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    return result
