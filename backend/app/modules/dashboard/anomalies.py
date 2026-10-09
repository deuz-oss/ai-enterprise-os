"""Penjelasan perubahan besar KPI dashboard (peluang AI #10 audit 2026-10-08).

Untuk KPI yang punya pembanding bulanan yang jujur, bandingkan dua bulan
PENUH terakhir (bukan bulan berjalan: MTD vs bulan penuh selalu tampak
turun). Semua dikelompokkan menurut bulan KEJADIAN (dibayar / diterbitkan /
difinalisasi), bukan bulan periode: invoice & payroll periode September
baru terbit/final di Oktober, sehingga pengelompokan per periode menampilkan
"turun 100%" palsu untuk bulan yang memang belum diproses. Bila berubah
>= `CHANGE_THRESHOLD`, kembalikan satu kalimat plus klien penyumbang selisih
terbesar sebagai sumber yang bisa ditelusuri.

Sengaja deterministik tanpa AI: dipanggil setiap dashboard dibuka, dan
kalimat templat sudah cukup -- yang dibutuhkan user adalah angka & sumbernya.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import ZERO, format_rupiah, to_decimal

CHANGE_THRESHOLD = Decimal("0.20")
# Abaikan perubahan pada angka kecil (mis. Rp200rb -> Rp100rb = -50%).
MIN_PREVIOUS = Decimal("1000000")
TOP_DRIVERS = 3
NO_CLIENT = "Tanpa klien"

MONTHS_ID = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]  # fmt: skip


def _last_two_full_months(today: date) -> tuple[tuple[int, int], tuple[int, int]]:
    y, m = today.year, today.month - 1
    if m == 0:
        y, m = y - 1, 12
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    return (y, m), (py, pm)


def _label(period: tuple[int, int]) -> str:
    return f"{MONTHS_ID[period[1] - 1]} {period[0]}"


def _client_names(db: Session, ids: Iterable[UUID | None]) -> dict[UUID | None, str]:
    from app.modules.clients.models import Client

    wanted = {i for i in ids if i is not None}
    names: dict[UUID | None, str] = {None: NO_CLIENT}
    if wanted:
        for cid, name in db.execute(select(Client.id, Client.name).where(Client.id.in_(wanted))):
            names[cid] = name
    return names


def _build(
    db: Session,
    *,
    key: str,
    label: str,
    link: str,
    current: tuple[int, int],
    previous: tuple[int, int],
    by_client: dict[tuple[int, int], dict[UUID | None, Decimal]],
) -> dict | None:
    cur = by_client.get(current, {})
    prev = by_client.get(previous, {})
    cur_total = sum(cur.values(), ZERO)
    prev_total = sum(prev.values(), ZERO)
    if prev_total < MIN_PREVIOUS:
        return None
    change = (cur_total - prev_total) / prev_total
    if abs(change) < CHANGE_THRESHOLD:
        return None

    names = _client_names(db, set(cur) | set(prev))
    deltas = [
        (cid, cur.get(cid, ZERO), prev.get(cid, ZERO))
        for cid in set(cur) | set(prev)
        if cur.get(cid, ZERO) != prev.get(cid, ZERO)
    ]
    # Penyumbang searah dengan perubahan total, selisih terbesar dulu.
    direction = 1 if change > 0 else -1
    deltas = [d for d in deltas if (d[1] - d[2]) * direction > 0]
    deltas.sort(key=lambda d: abs(d[1] - d[2]), reverse=True)
    drivers = [
        {
            "client_id": str(cid) if cid else None,
            "name": names.get(cid, NO_CLIENT),
            "current": float(c),
            "previous": float(p),
            "delta": float(c - p),
        }
        for cid, c, p in deltas[:TOP_DRIVERS]
    ]
    verb = "naik" if change > 0 else "turun"
    sentence = (
        f"{label} {_label(current)} {verb} {abs(change) * 100:.0f}% dari {_label(previous)} "
        f"({format_rupiah(prev_total)} → {format_rupiah(cur_total)})"
    )
    if deltas:
        top_id, top_cur, top_prev = deltas[0]
        top_delta = top_cur - top_prev
        sign = "+" if top_delta > 0 else "−"
        sentence += (
            f", terbesar dari {names.get(top_id, NO_CLIENT)} "
            f"({sign}{format_rupiah(abs(top_delta))})"
        )
    return {
        "kpi": key,
        "label": label,
        "period": _label(current),
        "compared_to": _label(previous),
        "current": float(cur_total),
        "previous": float(prev_total),
        "change_pct": float(change),
        "sentence": sentence + ".",
        "drivers": drivers,
        "link": link,
    }


def _revenue_collected(db: Session, periods: set[tuple[int, int]]) -> dict:
    from app.modules.finance.models import Invoice, InvoiceStatus

    earliest = min(periods)
    out: dict[tuple[int, int], dict[UUID | None, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    rows = db.execute(
        select(Invoice.client_id, Invoice.paid_at, Invoice.total_due).where(
            Invoice.status == InvoiceStatus.paid,
            Invoice.paid_at.is_not(None),
            Invoice.paid_at >= date(earliest[0], earliest[1], 1),
        )
    )
    for client_id, paid_at, total in rows:
        if paid_at is None:  # sudah difilter di query; penjaga tipe
            continue
        period = (paid_at.year, paid_at.month)
        if period in periods:
            out[period][client_id] += to_decimal(total)
    return out


def _billed(db: Session, periods: set[tuple[int, int]]) -> dict:
    from app.modules.finance.models import Invoice, InvoiceStatus

    out: dict[tuple[int, int], dict[UUID | None, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    earliest = min(periods)
    rows = db.execute(
        select(Invoice.client_id, Invoice.issued_date, Invoice.total_due).where(
            Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.paid]),
            Invoice.issued_date.is_not(None),
            Invoice.issued_date >= date(earliest[0], earliest[1], 1),
        )
    )
    for client_id, issued, total in rows:
        if issued is None:  # sudah difilter di query; penjaga tipe
            continue
        period = (issued.year, issued.month)
        if period in periods:
            out[period][client_id] += to_decimal(total)
    return out


def _payroll_gross(db: Session, periods: set[tuple[int, int]]) -> dict:
    from app.modules.hrd.models import Employee
    from app.modules.payroll.models import PayrollRun, PayrollRunStatus, Payslip
    from app.modules.recruitment.models import JobOrder, Placement

    out: dict[tuple[int, int], dict[UUID | None, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    rows = db.execute(
        select(
            PayrollRun.finalized_at,
            PayrollRun.client_id,
            JobOrder.client_id,
            Payslip.gross,
        )
        .join(Payslip, Payslip.run_id == PayrollRun.id)
        .join(Employee, Employee.id == Payslip.employee_id)
        .outerjoin(Placement, Placement.id == Employee.placement_id)
        .outerjoin(JobOrder, JobOrder.id == Placement.job_order_id)
        .where(PayrollRun.status == PayrollRunStatus.final, PayrollRun.finalized_at.is_not(None))
    )
    for finalized_at, run_client, placement_client, gross in rows:
        if finalized_at is None:  # sudah difilter di query; penjaga tipe
            continue
        period = (finalized_at.year, finalized_at.month)
        if period in periods:
            # Run proyek milik satu klien; run umum diatribusikan lewat placement.
            out[period][run_client or placement_client] += to_decimal(gross)
    return out


def kpi_anomalies(db: Session, today: date | None = None) -> dict:
    current, previous = _last_two_full_months(today or date.today())
    periods = {current, previous}
    specs = [
        ("revenue_collected", "Kas masuk dari invoice", "/finance", _revenue_collected),
        ("billed", "Nilai invoice diterbitkan", "/finance", _billed),
        ("payroll_gross", "Bruto payroll difinalisasi", "/payroll", _payroll_gross),
    ]
    items = []
    for key, label, link, source in specs:
        item = _build(
            db,
            key=key,
            label=label,
            link=link,
            current=current,
            previous=previous,
            by_client=source(db, periods),
        )
        if item:
            items.append(item)
    items.sort(key=lambda i: abs(i["change_pct"]), reverse=True)
    return {
        "period": _label(current),
        "compared_to": _label(previous),
        "threshold_pct": float(CHANGE_THRESHOLD),
        "items": items,
    }
