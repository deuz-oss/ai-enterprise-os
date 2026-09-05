"""SUPERSEDED (Fase 28): laporan estimasi Opsi F, dipertahankan untuk
riwayat/rujukan platform-admin (ADR-0007 poin 3) -- bukan lagi sumber
penagihan aktif. Ledger nyata sekarang `credit_transactions`, ditulis
real-time oleh `billing/service.py::record_credit_transaction` (event-based)
dan `billing/cycle_close.py` (periodik), bukan dihitung ulang tiap panggilan.

Laporan estimasi pemakaian & tagihan per tenant — PRD v3.0 §2 (Opsi F metered).

Read-only: tidak menagih, tidak menyimpan riwayat, tidak terhubung ke
pembayaran. Dihitung ulang tiap panggilan untuk periode yang diminta.

Berjalan di bawah /platform (platform_admin, tanpa konteks tenant aktif) —
setiap query eksplisit `tenant_id == ...` DAN `compute_usage()` men-set
konteks tenant secara manual sebelum query (wajib untuk Postgres RLS,
bukan cuma filter ORM -- lihat docstring `compute_usage()`).

Belum tercakup (lihat diskusi PRD v3.0 §2):
- Shadow billing talent nonaktif >180 hari (butuh field `last_match_at`
  yang belum ada di skema) — talent aktif dihitung sederhana:
  `tp_status in (baru, diproses)` tanpa masa tenggang.
- Govern Cloud: PRD memberi rentang harga (5-7jt), bukan angka pasti —
  tidak ada field harga per tenant, jadi baris ini selalu `amount=None`.
- AI Add-on: pemakaian token tidak diinstrumentasi di titik panggil LLM
  manapun — baris ini selalu `amount=None`.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.platform.models import LicenseStatus, TenantAppLicense
from app.modules.platform.service import _get_tenant

_ACTIVE_LICENSE_STATUSES = (LicenseStatus.active, LicenseStatus.trial)


def _period_bounds(period: str | None) -> tuple[str, date, date]:
    if period:
        year_s, month_s = period.split("-")
        year, month = int(year_s), int(month_s)
    else:
        today = date.today()
        year, month = today.year, today.month
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return f"{year:04d}-{month:02d}", start, end


def _licensed_keys(db: Session, tenant_id: UUID) -> set[str]:
    rows = db.execute(
        select(TenantAppLicense.app_key).where(
            TenantAppLicense.tenant_id == tenant_id,
            TenantAppLicense.status.in_(_ACTIVE_LICENSE_STATUSES),
        )
    ).scalars()
    return set(rows)


def _talent_active_count(db: Session, tenant_id: UUID) -> int:
    """talent aktif = kandidat belum arsip DAN status talentpool terakhirnya
    bukan placed/non_aktif. Tanpa masa tenggang 180 hari (lihat catatan modul)."""
    from app.modules.recruitment.models import Candidate, CandidateStatus
    from app.modules.talentpool.models import CvIntake, TalentPoolStatus

    latest_by_candidate: dict[UUID, CvIntake] = {}
    for intake in db.execute(
        select(CvIntake).where(CvIntake.tenant_id == tenant_id).order_by(CvIntake.created_at.asc())
    ).scalars():
        latest_by_candidate[intake.candidate_id] = intake  # naik → terakhir menang

    inactive_ids = {
        cid
        for cid, intake in latest_by_candidate.items()
        if intake.tp_status in (TalentPoolStatus.placed, TalentPoolStatus.non_aktif)
    }
    stmt = select(func.count(Candidate.id)).where(
        Candidate.tenant_id == tenant_id, Candidate.status != CandidateStatus.archived
    )
    if inactive_ids:
        stmt = stmt.where(Candidate.id.notin_(inactive_ids))
    return db.execute(stmt).scalar() or 0


def _audit_action_count(db: Session, tenant_id: UUID, action: str, start: date, end: date) -> int:
    from app.modules.audit.models import AuditLog

    return (
        db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action == action,
                AuditLog.created_at >= start,
                AuditLog.created_at < end + timedelta(days=1),
            )
        ).scalar()
        or 0
    )


def _employee_active_count(db: Session, tenant_id: UUID) -> int:
    from app.modules.hrd.models import Employee, EmployeeStatus

    return (
        db.execute(
            select(func.count(Employee.id)).where(
                Employee.tenant_id == tenant_id, Employee.status == EmployeeStatus.active
            )
        ).scalar()
        or 0
    )


def _invoices_this_period(db: Session, tenant_id: UUID, start: date, end: date) -> int:
    from app.modules.finance.models import Invoice

    return (
        db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.tenant_id == tenant_id,
                Invoice.issued_date.is_not(None),
                Invoice.issued_date >= start,
                Invoice.issued_date <= end,
            )
        ).scalar()
        or 0
    )


def compute_usage(db: Session, tenant_id: UUID, period: str | None = None) -> dict:
    """Estimasi pemakaian & tagihan satu tenant untuk satu periode (YYYY-MM).

    Hanya menyertakan baris untuk SKU yang benar-benar berlisensi (aktif/trial)
    — SKU yang tidak dipakai tidak muncul sebagai baris nol.

    Dipanggil dari konteks platform_admin (tanpa tenant aktif) untuk
    tenant_id ARBITRARY lewat path param -- `set_tenant()` WAJIB di sini
    walau setiap query di bawah sudah eksplisit `.where(tenant_id == ...)`,
    karena itu cuma cukup untuk filter ORM otomatis, BUKAN untuk Postgres
    RLS (server-side, independen dari klausa WHERE manapun di query itu
    sendiri). Tanpa ini, di Postgres+RLS semua query di bawah pulang KOSONG
    (bug ditemukan &amp; diperbaiki bareng audit Fase 28, 2026-09-05).
    """
    from app.core.tenancy import get_tenant, set_tenant

    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        return _compute_usage_locked(db, tenant_id, period)
    finally:
        set_tenant(previous_tenant)


def _compute_usage_locked(db: Session, tenant_id: UUID, period: str | None) -> dict:
    tenant = _get_tenant(db, tenant_id)
    period_str, start, end = _period_bounds(period)
    licensed = _licensed_keys(db, tenant_id)

    lines: list[dict] = []
    total_known = 0.0

    if "sales_crm" in licensed or "recruitment" in licensed:
        talent_qty = _talent_active_count(db, tenant_id)
        talent_amount = talent_qty * 15_000
        lines.append(
            {
                "sku": "talent",
                "label": "Talent Cloud — talent aktif",
                "metric": "talent aktif",
                "qty": talent_qty,
                "rate": 15_000,
                "amount": talent_amount,
            }
        )
        total_known += talent_amount

        match_qty = _audit_action_count(db, tenant_id, "recruitment.match_executed", start, end)
        match_amount = match_qty * 2_000
        lines.append(
            {
                "sku": "talent",
                "label": "Talent Cloud — match execution",
                "metric": "match execution",
                "qty": match_qty,
                "rate": 2_000,
                "amount": match_amount,
            }
        )
        total_known += match_amount

    if "people_ops" in licensed:
        emp_qty = _employee_active_count(db, tenant_id)
        emp_amount = emp_qty * 10_000
        lines.append(
            {
                "sku": "workforce",
                "label": "Workforce Cloud",
                "metric": "employee aktif",
                "qty": emp_qty,
                "rate": 10_000,
                "amount": emp_amount,
            }
        )
        total_known += emp_amount

    if "payroll" in licensed or "finance" in licensed:
        inv_qty = _invoices_this_period(db, tenant_id, start, end)
        faktur_qty = _audit_action_count(db, tenant_id, "invoice.tax_invoice_sent", start, end)
        base = 1_000_000
        revenue_amount = inv_qty * 5_000 + faktur_qty * 8_000 + base
        lines.append(
            {
                "sku": "revenue",
                "label": "Revenue Cloud",
                "metric": "invoice+faktur",
                "qty_invoice": inv_qty,
                "qty_faktur": faktur_qty,
                "base": base,
                "amount": revenue_amount,
            }
        )
        total_known += revenue_amount

    if "accounting" in licensed:
        lines.append(
            {
                "sku": "govern",
                "label": "Govern Cloud",
                "metric": "flat",
                "amount": None,
                "note": "Harga flat (5-7jt) belum dikonfigurasi per tenant",
            }
        )

    if "ai_addon" in licensed:
        lines.append(
            {
                "sku": "ai_addon",
                "label": "AI Add-on",
                "metric": "token",
                "amount": None,
                "note": "Pemakaian token belum diinstrumentasi",
            }
        )

    return {
        "tenant_id": str(tenant.id),
        "period": period_str,
        "billing_mode": tenant.billing_mode,
        "lines": lines,
        "total_known": total_known,
    }
