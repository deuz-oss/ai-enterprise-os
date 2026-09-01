"""Forecast arus kas bulanan.

Angka proyeksi dihitung deterministik di Python (tren linier sederhana per
komponen masuk/keluar); LLM hanya menyusun narasi, risiko, dan rekomendasi
agar angka yang ditampilkan tetap dapat diaudit.
"""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import chat_completion
from app.modules.ai.schemas import ForecastOut, MonthlyFlow
from app.modules.finance.models import (
    CashFlowDirection,
    CashFlowEntry,
    Invoice,
    InvoiceStatus,
)

_HISTORY_MONTHS = 6
_BASELINE_MONTHS = 4  # bulan lengkap terakhir yang dipakai regresi
_MAX_MONTHS_AHEAD = 12

_SYSTEM_PROMPT = (
    "Anda analis keuangan untuk perusahaan outsourcing Indonesia. Berdasarkan "
    "riwayat arus kas dan proyeksi tren linier yang diberikan, berikan analisis "
    "singkat. Balas HANYA JSON valid dengan skema: "
    '{"outlook": "<positif|netral|negatif>", "summary": "<ringkasan 2-3 kalimat '
    'bahasa Indonesia>", "risks": ["<risiko arus kas>"], '
    '"recommendations": ["<rekomendasi konkret>"]}. Jangan mengubah angka '
    "proyeksi; fokus pada interpretasi."
)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _month_span(start: tuple[int, int], count: int) -> list[tuple[int, int]]:
    return [_shift_month(start[0], start[1], i) for i in range(count)]


def _linear_projection(values: list[float]) -> float:
    """Proyeksi satu bulan ke depan memakai regresi linier sederhana."""
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return values[0]
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in range(n))
    slope = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values)) / denom
    # Titik berikutnya: x = n
    return mean_y + slope * (n - mean_x)


def forecast_cash_flow(db: Session, months_ahead: int = 3) -> ForecastOut:
    months_ahead = max(1, min(months_ahead, _MAX_MONTHS_AHEAD))
    today = date.today()
    current = (today.year, today.month)

    hist_start = _shift_month(current[0], current[1], -(_HISTORY_MONTHS - 1))
    first_of_hist = date(hist_start[0], hist_start[1], 1)
    entries = list(
        db.scalars(select(CashFlowEntry).where(CashFlowEntry.entry_date >= first_of_hist)).all()
    )

    buckets: dict[tuple[int, int], list[float]] = {
        key: [0.0, 0.0] for key in _month_span(hist_start, _HISTORY_MONTHS)
    }
    for entry in entries:
        key = (entry.entry_date.year, entry.entry_date.month)
        if key not in buckets:
            continue
        idx_bucket = 0 if entry.direction == CashFlowDirection.inflow else 1
        buckets[key][idx_bucket] += float(entry.amount)

    history = [
        MonthlyFlow(year=y, month=m, inflow=b[0], outflow=b[1], net=b[0] - b[1])
        for (y, m), b in sorted(buckets.items())
    ]

    # Bulan berjalan diabaikan dari baseline karena belum bulan penuh.
    baseline_keys = [key for key in _month_span(hist_start, _HISTORY_MONTHS)[:-1]][
        -_BASELINE_MONTHS:
    ]
    inflow_series = [buckets[key][0] for key in baseline_keys]
    outflow_series = [buckets[key][1] for key in baseline_keys]

    projection: list[MonthlyFlow] = []
    for i in range(1, months_ahead + 1):
        y, m = _shift_month(current[0], current[1], i)
        days = calendar.monthrange(y, m)[1]
        inflow = max(0.0, round(_linear_projection(inflow_series)))
        outflow = max(0.0, round(_linear_projection(outflow_series)))
        # Normalisasi panjang bulan (28-31 hari) agar tren tidak bias jumlah hari.
        factor = days / 30.44
        projection.append(
            MonthlyFlow(
                year=y,
                month=m,
                inflow=round(inflow * factor),
                outflow=round(outflow * factor),
                net=round((inflow - outflow) * factor),
            )
        )

    pending = float(
        db.scalar(
            select(func.coalesce(func.sum(Invoice.total_due), 0.0)).where(
                Invoice.status == InvoiceStatus.sent
            )
        )
        or 0.0
    )

    history_lines = "\n".join(
        f"- {h.year}-{h.month:02d}: masuk {h.inflow:,.0f}, keluar {h.outflow:,.0f}, "
        f"net {h.net:,.0f}"
        for h in history
    )
    proj_lines = "\n".join(
        f"- {p.year}-{p.month:02d}: masuk {p.inflow:,.0f}, keluar {p.outflow:,.0f}, "
        f"net {p.net:,.0f}"
        for p in projection
    )
    user_prompt = (
        f"HISTORI ARUS KAS ({_HISTORY_MONTHS} bulan terakhir):\n{history_lines}\n\n"
        f"PROYEKSI TREN LINIER ({months_ahead} bulan ke depan):\n{proj_lines}\n\n"
        f"Piutang belum tertagih (invoice terkirim): Rp{pending:,.0f}\n\n"
        "Berikan analisisnya."
    )
    result = chat_completion(_SYSTEM_PROMPT, user_prompt, json_mode=True, feature="ai.forecast")
    data = result if isinstance(result, dict) else {}

    outlook = str(data.get("outlook") or "netral").lower()
    if outlook not in ("positif", "netral", "negatif"):
        outlook = "netral"
    raw_risks = data.get("risks")
    risks = [str(r) for r in raw_risks][:8] if isinstance(raw_risks, list) else []
    raw_recs = data.get("recommendations")
    recs = [str(r) for r in raw_recs][:8] if isinstance(raw_recs, list) else []

    return ForecastOut(
        history=history,
        projection=projection,
        pending_receivables=pending,
        outlook=outlook,
        summary=str(data.get("summary") or "").strip() or "-",
        risks=risks,
        recommendations=recs,
        model=get_settings().ai_model,
    )
