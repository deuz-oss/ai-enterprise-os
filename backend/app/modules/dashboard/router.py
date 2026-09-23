from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_tenant_user
from app.modules.clients.models import Client, LegalDocument
from app.modules.presales.models import Lead, LeadStage
from app.modules.recruitment.models import Candidate, JobOrder, JobOrderStatus

# Agregat lintas modul — platform_admin diblokir agar tidak melihat data tenant.
router = APIRouter(
    prefix="/overview",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)


def _forbid_karyawan(user=Depends(get_current_user)):
    """Agregat bisnis (revenue, piutang, pipeline, klien) bukan untuk akun
    karyawan outsourcing -- dulu cukup login utk membacanya. Karyawan
    memakai `/overview/personal` (UI sudah mengarahkan ke Portal Saya)."""
    if getattr(user.role, "value", user.role) == "karyawan":
        raise HTTPException(
            status_code=403, detail="Dashboard perusahaan bukan untuk akun karyawan"
        )
    return user


@router.get("", dependencies=[Depends(_forbid_karyawan)])
def overview(db: Session = Depends(get_db)):
    """Dashboard Umum PRD v2.0 — 8 widget cross-bundle + AI insight stub.

    Internal mode: semua data agregat tanpa filter bundle.
    Commercial mode: frontend tetap hit endpoint yang sama, tapi widget
    bundle non-aktif menampilkan upsell (di-handle FE via /apps).
    """
    # --- Sales CRM ---
    lead_rows = db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all()
    leads = {stage.value: count for stage, count in lead_rows}
    # Nilai pipeline (Rp) -- "sinyal bisnis apa yang belum muncul" (audit
    # desain 2026-09-15): dashboard sebelumnya cuma hitung JUMLAH lead per
    # tahap, tidak pernah nilai Rp-nya, padahal field-nya sudah ada
    # (Lead.estimated_value + fx_rate_to_idr, dipakai Leads.tsx sbg "Total
    # Nilai Pipeline"). Dijumlah di Python (bukan SQL SUM langsung) supaya
    # logika "estimated_value * fx_rate_to_idr, fallback 1" identik persis
    # dgn property `Lead.estimated_value_idr` -- exclude won/lost, sama
    # seperti `activeLeads` di Leads.tsx (pipeline = yang masih berjalan).
    pipeline_value_idr = 0.0
    for est_value, fx_rate in db.execute(
        select(Lead.estimated_value, Lead.fx_rate_to_idr).where(
            Lead.stage.notin_([LeadStage.won, LeadStage.lost])
        )
    ).all():
        pipeline_value_idr += float(est_value or 0) * float(fx_rate or 1)
    open_job_orders = (
        db.execute(
            select(func.count(JobOrder.id)).where(
                JobOrder.status.notin_([JobOrderStatus.filled, JobOrderStatus.closed])
            )
        ).scalar()
        or 0
    )
    candidate_rows = db.execute(
        select(Candidate.status, func.count(Candidate.id)).group_by(Candidate.status)
    ).all()
    candidates = {status_.value: count for status_, count in candidate_rows}

    # --- People & Operations (HR) ---
    try:
        from app.modules.hrd.models import Employee, EmployeeStatus

        total_employees = db.execute(select(func.count(Employee.id))).scalar() or 0
        active_employees = (
            db.execute(
                select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.active)
            ).scalar()
            or 0
        )
        # Turnover BULAN INI -- "sinyal bisnis apa yang belum muncul" (audit
        # desain 2026-09-15): sebelumnya cuma ada hitungan statis total
        # resign sepanjang masa (tidak actionable), sekarang bisa per
        # periode krn `Employee.resigned_at` baru ditambah (lihat models.py
        # & migrasi 5e6f7a8b9c0d). Baris resign LAMA (sebelum kolom ini ada)
        # sengaja tidak dihitung di sini -- resigned_at-nya NULL, bukan
        # backfill tebakan.
        resigned_this_month = 0
        try:
            month_start = date.today().replace(day=1)
            resigned_this_month = (
                db.execute(
                    select(func.count(Employee.id)).where(
                        Employee.status == EmployeeStatus.resigned,
                        Employee.resigned_at.is_not(None),
                        Employee.resigned_at >= month_start,
                    )
                ).scalar()
                or 0
            )
        except Exception:
            db.rollback()
        # Dokumen expiry ≤14 hari & BPJS/asuransi completeness
        expiring_contracts = 0
        try:
            from app.modules.hrd.models import EmploymentContract

            cutoff = date.today() + timedelta(days=14)
            expiring_contracts = (
                db.execute(
                    select(func.count(EmploymentContract.id)).where(
                        EmploymentContract.end_date.is_not(None),
                        EmploymentContract.end_date <= cutoff,
                        EmploymentContract.end_date >= date.today(),
                    )
                ).scalar()
                or 0
            )
        except Exception:
            db.rollback()
        # BPJS & asuransi completeness (field baru PRD v2.0 — fallback 0 jika kolom belum migrasi)
        bpjs_complete = 0
        insurance_complete = 0
        try:
            bpjs_complete = (
                db.execute(
                    select(func.count(Employee.id)).where(
                        Employee.bpjs_kesehatan_no.is_not(None), Employee.bpjs_kesehatan_no != ""
                    )
                ).scalar()
                or 0
            )
            # Employee.insurance_policy_no adalah kolom lama PRD v2.0 yang
            # sudah tidak diisi UI (digantikan tabel one-to-many
            # EmployeeInsurance PRD v3.0) — hitung dari situ, bukan kolom mati.
            from app.modules.hrd.models import EmployeeInsurance

            insurance_complete = (
                db.execute(
                    select(func.count(func.distinct(EmployeeInsurance.employee_id))).where(
                        EmployeeInsurance.status == "aktif"
                    )
                ).scalar()
                or 0
            )
        except Exception:
            db.rollback()
    except Exception:
        db.rollback()
        total_employees = active_employees = expiring_contracts = bpjs_complete = (
            insurance_complete
        ) = resigned_this_month = 0

    # --- Payroll ---
    # PayrollRunStatus asli: draft/submitted_to_client/client_rejected/
    # client_approved/finance_processing/final — dipetakan ke 4 bucket
    # widget (draft/submitted/approved/finalized). Regresi: dict lama diisi
    # pakai key salah ("submitted"/"approved"/"finalized") yang tidak pernah
    # cocok dgn value enum sungguhan, jadi selalu 0 kecuali "draft".
    payroll_summary = {"draft": 0, "submitted": 0, "approved": 0, "finalized": 0}
    _PAYROLL_STATUS_BUCKET = {
        "draft": "draft",
        "submitted_to_client": "submitted",
        "client_rejected": "submitted",
        "client_approved": "approved",
        "finance_processing": "approved",
        "final": "finalized",
    }
    try:
        from app.modules.payroll.models import PayrollRun

        for st, cnt in db.execute(
            select(PayrollRun.status, func.count(PayrollRun.id)).group_by(PayrollRun.status)
        ).all():
            key = st.value if hasattr(st, "value") else str(st)
            bucket = _PAYROLL_STATUS_BUCKET.get(key, key)
            payroll_summary[bucket] = payroll_summary.get(bucket, 0) + cnt
    except Exception:
        db.rollback()

    # --- Finance ---
    finance_summary: dict[str, float] = {
        "revenue_mtd": 0,
        "outstanding": 0,
        "overdue": 0,
        "invoices_total": 0,
    }
    try:
        from app.modules.finance.models import Invoice, InvoiceStatus

        finance_summary["invoices_total"] = db.execute(select(func.count(Invoice.id))).scalar() or 0
        month_start = date.today().replace(day=1)
        finance_summary["revenue_mtd"] = (
            db.execute(
                select(func.coalesce(func.sum(Invoice.total_due), 0)).where(
                    Invoice.status == InvoiceStatus.paid,
                    Invoice.paid_at.is_not(None),
                    Invoice.paid_at >= month_start,
                )
            ).scalar()
            or 0
        )
        finance_summary["outstanding"] = (
            db.execute(
                select(func.coalesce(func.sum(Invoice.total_due), 0)).where(
                    Invoice.status == InvoiceStatus.sent
                )
            ).scalar()
            or 0
        )
        # Overdue = sent + due_date < today
        finance_summary["overdue"] = (
            db.execute(
                select(func.count(Invoice.id)).where(
                    Invoice.status == InvoiceStatus.sent,
                    Invoice.due_date.is_not(None),
                    Invoice.due_date < date.today(),
                )
            ).scalar()
            or 0
        )
        # Faktur pajak PRD v2.0
        try:
            faktur_belum = (
                db.execute(
                    select(func.count(Invoice.id)).where(
                        (Invoice.tax_invoice_status.is_(None))
                        | (Invoice.tax_invoice_status == "belum_buat")
                    )
                ).scalar()
                or 0
            )
            finance_summary["faktur_belum"] = int(faktur_belum)
        except Exception:
            db.rollback()
            finance_summary["faktur_belum"] = 0
    except Exception:
        db.rollback()

    # --- Accounting health ---
    accounting_health = {"period_closed": 0, "memorial_unposted": 0}
    try:
        from app.modules.accounting.models import AccountingPeriod, JournalEntry

        accounting_health["period_closed"] = (
            db.execute(select(func.count(AccountingPeriod.id))).scalar() or 0
        )
        try:
            accounting_health["memorial_unposted"] = (
                db.execute(
                    select(func.count(JournalEntry.id)).where(JournalEntry.status == "memorial")
                ).scalar()
                or 0
            )
        except Exception:
            db.rollback()
    except Exception:
        db.rollback()

    # --- Recruitment & Talent (widget 3): JO progress bar + interview minggu ini ---
    job_orders_by_stage = {s.value: 0 for s in JobOrderStatus}
    for st, cnt in db.execute(
        select(JobOrder.status, func.count(JobOrder.id)).group_by(JobOrder.status)
    ).all():
        job_orders_by_stage[st.value] = cnt
    interviews_this_week = 0
    try:
        from app.modules.recruitment.models import InterviewSchedule, InterviewStatus

        today = date.today()
        week_end = today + timedelta(days=7)
        interviews_this_week = (
            db.execute(
                select(func.count(InterviewSchedule.id)).where(
                    InterviewSchedule.status == InterviewStatus.scheduled,
                    InterviewSchedule.scheduled_at >= today,
                    InterviewSchedule.scheduled_at <= week_end,
                )
            ).scalar()
            or 0
        )
    except Exception:
        db.rollback()

    # --- Operations & Projects (widget 5): placement aktif per klien + margin ---
    active_placements_by_client: list[dict] = []
    try:
        from app.modules.recruitment.models import Placement, PlacementStatus

        rows = db.execute(
            select(Client.name, func.count(Placement.id))
            .join(JobOrder, Placement.job_order_id == JobOrder.id)
            .join(Client, JobOrder.client_id == Client.id)
            .where(Placement.status == PlacementStatus.onboarded)
            .group_by(Client.name)
            .order_by(func.count(Placement.id).desc())
        ).all()
        active_placements_by_client = [
            {"client": name, "active_placements": int(cnt)} for name, cnt in rows
        ]
    except Exception:
        db.rollback()
    profit_by_client_rows: list[dict] = []
    try:
        from app.modules.accounting.service import profit_by_client as _profit_by_client

        today = date.today()
        profit_by_client_rows = _profit_by_client(db, year=today.year, month=today.month)
    except Exception:
        db.rollback()

    # --- Revenue trend, 6 bulan terakhir termasuk bulan berjalan ---
    # Ditambah atas permintaan user (audit desain Dashboard 2026-09-15):
    # sebelumnya cuma ada revenue_mtd (1 angka), tidak cukup utk grafik
    # tren yang FE minta. Bucketing dilakukan di Python (bukan SQL
    # date_trunc/strftime) supaya portable lintas SQLite (dev) & Postgres
    # (docker/prod) -- dua dialek fungsi tanggal itu tidak saling kompatibel
    # dan tidak ada satu pun query month-grouping lain di codebase ini yang
    # bisa dicontoh secara aman.
    revenue_by_month: list[dict] = []
    try:
        from app.modules.finance.models import Invoice, InvoiceStatus

        today = date.today()
        month_starts: list[date] = []
        y, m = today.year, today.month
        for _ in range(6):
            month_starts.append(date(y, m, 1))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_starts.reverse()
        earliest = month_starts[0]

        paid_rows = db.execute(
            select(Invoice.paid_at, Invoice.total_due).where(
                Invoice.status == InvoiceStatus.paid,
                Invoice.paid_at.is_not(None),
                Invoice.paid_at >= earliest,
            )
        ).all()
        buckets = {(d.year, d.month): 0.0 for d in month_starts}
        for paid_at, total_due in paid_rows:
            key = (paid_at.year, paid_at.month)
            if key in buckets:
                buckets[key] += float(total_due or 0)
        revenue_by_month = [
            {"month": d.strftime("%Y-%m"), "revenue": buckets[(d.year, d.month)]}
            for d in month_starts
        ]
    except Exception:
        db.rollback()

    return {
        "leads": {
            "total": sum(leads.values()),
            "won": leads.get(LeadStage.won.value, 0),
            "lost": leads.get(LeadStage.lost.value, 0),
            "by_stage": leads,
            "funnel": [{"stage": s.value, "count": leads.get(s.value, 0)} for s in LeadStage],
            "pipeline_value_idr": pipeline_value_idr,
        },
        "clients": db.execute(select(func.count(Client.id))).scalar() or 0,
        "documents": db.execute(select(func.count(LegalDocument.id))).scalar() or 0,
        "job_orders": {
            "open": int(open_job_orders),
            "filled": int(
                db.execute(
                    select(func.count(JobOrder.id)).where(JobOrder.status == JobOrderStatus.filled)
                ).scalar()
                or 0
            ),
        },
        "candidates": {"total": sum(candidates.values()), "by_status": candidates},
        # PRD v2.0 — 8 widget tambahan
        "people": {
            "total_employees": int(total_employees),
            "active_employees": int(active_employees),
            "expiring_contracts_14d": int(expiring_contracts),
            "bpjs_complete": int(bpjs_complete),
            "insurance_complete": int(insurance_complete),
            "resigned_this_month": int(resigned_this_month),
        },
        "payroll": payroll_summary,
        "finance": {**finance_summary, "revenue_by_month": revenue_by_month},
        "accounting": accounting_health,
        "recruitment_talent": {
            "job_orders_by_stage": job_orders_by_stage,
            "interviews_this_week": int(interviews_this_week),
        },
        "operations": {
            "active_placements_by_client": active_placements_by_client,
            "profit_by_client": profit_by_client_rows,
        },
        "ai_insight": {
            "hint": (
                "Gunakan GET /accounting/ai/executive-summary dan "
                "GET /chat/digest untuk narasi & tasks"
            ),
        },
    }


@router.get("/personal")
def overview_personal(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """PRD v3.0 — ringkas personal untuk karyawan (ESS) — hanya data milik sendiri."""
    from app.modules.hrd.models import Employee

    emp = db.execute(select(Employee).where(Employee.user_id == user.id)).scalar_one_or_none()
    if emp is None:
        return {"employee": None, "message": "Belum tertaut ke data karyawan"}

    # Kontrak expiry personal
    expiring = 0
    try:
        from app.modules.hrd.models import EmploymentContract

        cutoff = date.today() + timedelta(days=14)
        expiring = (
            db.execute(
                select(func.count(EmploymentContract.id)).where(
                    EmploymentContract.employee_id == emp.id,
                    EmploymentContract.end_date.is_not(None),
                    EmploymentContract.end_date <= cutoff,
                )
            ).scalar()
            or 0
        )
    except Exception:
        db.rollback()

    # Slip terakhir
    payslip_count = 0
    try:
        from app.modules.payroll.models import Payslip

        payslip_count = (
            db.execute(select(func.count(Payslip.id)).where(Payslip.employee_id == emp.id)).scalar()
            or 0
        )
    except Exception:
        db.rollback()

    return {
        "employee": {
            "id": str(emp.id),
            "full_name": emp.full_name,
            "status": emp.status.value if hasattr(emp.status, "value") else str(emp.status),
        },
        "expiring_contracts_14d": int(expiring),
        "payslips_total": int(payslip_count),
        "bpjs": {
            "kesehatan_no": emp.bpjs_kesehatan_no,
            "ketenagakerjaan_no": emp.bpjs_ketenagakerjaan_no,
        },
    }
