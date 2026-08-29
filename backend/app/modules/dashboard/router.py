from datetime import date, timedelta

from fastapi import APIRouter, Depends
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


@router.get("")
def overview(db: Session = Depends(get_db)):
    """Dashboard Umum PRD v2.0 — 8 widget cross-bundle + AI insight stub.

    Internal mode: semua data agregat tanpa filter bundle.
    Commercial mode: frontend tetap hit endpoint yang sama, tapi widget
    bundle non-aktif menampilkan upsell (di-handle FE via /apps).
    """
    # --- Sales CRM ---
    lead_rows = db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all()
    leads = {stage.value: count for stage, count in lead_rows}
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
            pass
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
            insurance_complete = (
                db.execute(
                    select(func.count(Employee.id)).where(
                        Employee.insurance_policy_no.is_not(None),
                        Employee.insurance_policy_no != "",
                    )
                ).scalar()
                or 0
            )
        except Exception:
            pass
    except Exception:
        total_employees = active_employees = expiring_contracts = bpjs_complete = (
            insurance_complete
        ) = 0

    # --- Payroll ---
    payroll_summary = {"draft": 0, "submitted": 0, "approved": 0, "finalized": 0}
    try:
        from app.modules.payroll.models import PayrollRun

        for st, cnt in db.execute(
            select(PayrollRun.status, func.count(PayrollRun.id)).group_by(PayrollRun.status)
        ).all():
            payroll_summary[st.value if hasattr(st, "value") else str(st)] = cnt
    except Exception:
        pass

    # --- Finance ---
    finance_summary = {"revenue_mtd": 0, "outstanding": 0, "overdue": 0, "invoices_total": 0}
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
            finance_summary["faktur_belum"] = 0
    except Exception:
        pass

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
            pass
    except Exception:
        pass

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
        pass

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
        pass
    profit_by_client_rows: list[dict] = []
    try:
        from app.modules.accounting.service import profit_by_client as _profit_by_client

        today = date.today()
        profit_by_client_rows = _profit_by_client(db, year=today.year, month=today.month)
    except Exception:
        pass

    return {
        "leads": {
            "total": sum(leads.values()),
            "won": leads.get(LeadStage.won.value, 0),
            "by_stage": leads,
            "funnel": [{"stage": s.value, "count": leads.get(s.value, 0)} for s in LeadStage],
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
        },
        "payroll": payroll_summary,
        "finance": finance_summary,
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
        pass

    # Slip terakhir
    payslip_count = 0
    try:
        from app.modules.payroll.models import Payslip

        payslip_count = (
            db.execute(select(func.count(Payslip.id)).where(Payslip.employee_id == emp.id)).scalar()
            or 0
        )
    except Exception:
        pass

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
