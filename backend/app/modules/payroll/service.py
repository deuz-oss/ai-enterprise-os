from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules.hrd.models import Employee, EmployeeStatus
from app.modules.payroll.models import (
    AttendanceSummary,
    PayrollRun,
    PayrollRunStatus,
    Payslip,
)
from app.modules.payroll.schemas import (
    AttendanceUpsert,
    GenerateSlipsRequest,
    RunCreate,
    TaxPreviewIn,
)
from app.modules.payroll.tax import TaxProfile, compute_pasal17_monthly_average, compute_ter

# ---------- Attendance & approval klien ----------


def upsert_attendance(db: Session, payload: AttendanceUpsert) -> AttendanceSummary:
    if db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    summary = db.execute(
        select(AttendanceSummary).where(
            AttendanceSummary.employee_id == payload.employee_id,
            AttendanceSummary.year == payload.year,
            AttendanceSummary.month == payload.month,
        )
    ).scalar_one_or_none()
    if summary is None:
        summary = AttendanceSummary(**payload.model_dump())
        db.add(summary)
    else:
        for field in ("present_days", "overtime_hours", "notes"):
            setattr(summary, field, getattr(payload, field))
        # Perubahan data me-reset approval klien agar diverifikasi ulang.
        summary.client_approved = False
        summary.approved_at = None
    db.commit()
    db.refresh(summary)
    return summary


def set_client_approval(
    db: Session, attendance_id: str, approved: bool
) -> AttendanceSummary:
    summary = db.get(AttendanceSummary, parse_uuid(attendance_id))
    if summary is None:
        raise HTTPException(status_code=404, detail="Rekap absensi tidak ditemukan")
    summary.client_approved = approved
    summary.approved_at = datetime.now(UTC) if approved else None
    db.commit()
    db.refresh(summary)
    return summary


def list_attendance(db: Session, year: int, month: int) -> list[AttendanceSummary]:
    stmt = (
        select(AttendanceSummary)
        .where(AttendanceSummary.year == year, AttendanceSummary.month == month)
        .order_by(AttendanceSummary.created_at)
    )
    return list(db.execute(stmt).scalars())


# ---------- Payroll runs ----------


def _get_run(db: Session, run_id: str) -> PayrollRun:
    run = db.get(PayrollRun, parse_uuid(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run tidak ditemukan")
    return run


def create_run(db: Session, payload: RunCreate) -> PayrollRun:
    duplicate = db.execute(
        select(PayrollRun).where(PayrollRun.year == payload.year, PayrollRun.month == payload.month)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=409, detail=f"Payrol periode {payload.year}-{payload.month} sudah ada"
        )
    run = PayrollRun(year=payload.year, month=payload.month)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_runs(db: Session) -> list[PayrollRun]:
    stmt = select(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    return list(db.execute(stmt).scalars())


def get_run(db: Session, run_id: str) -> PayrollRun:
    return _get_run(db, run_id)


def list_slips(db: Session, run_id: str) -> list[Payslip]:
    run = _get_run(db, run_id)
    return list(run.slips)


def generate_slips(db: Session, run_id: str, payload: GenerateSlipsRequest) -> list[Payslip]:
    """Buat slip gaji untuk karyawan aktif; hanya lembur yang disetujui klien."""
    run = _get_run(db, run_id)
    if run.status == PayrollRunStatus.final:
        raise HTTPException(status_code=409, detail="Payroll run sudah final dan terkunci")

    employee_stmt = select(Employee).where(Employee.status == EmployeeStatus.active)
    if payload.employee_ids:
        ids = [parse_uuid(str(e)) for e in payload.employee_ids]
        employee_stmt = employee_stmt.where(Employee.id.in_(ids))
    employees = list(db.execute(employee_stmt).scalars())
    if not employees:
        raise HTTPException(status_code=422, detail="Tidak ada karyawan aktif untuk diproses")

    summaries = {
        s.employee_id: s
        for s in db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.year == run.year, AttendanceSummary.month == run.month
            )
        ).scalars()
    }

    slips: list[Payslip] = []
    skipped_unapproved = 0
    for employee in employees:
        overtime_hours = 0
        summary = summaries.get(employee.id)
        if summary is not None and summary.overtime_hours:
            if not summary.client_approved:
                skipped_unapproved += 1
            else:
                overtime_hours = summary.overtime_hours

        base = float(employee.base_salary or 0)
        overtime_amount = overtime_hours * float(payload.overtime_rate or 0)
        gross = base + float(payload.allowance or 0) + overtime_amount

        profile = TaxProfile(
            marital_status=(employee.marital_status.value if employee.marital_status else "tk"),
            dependents=employee.dependents or 0,
        )
        tax = compute_ter(gross, profile)

        slip = Payslip(
            run_id=run.id,
            employee_id=employee.id,
            base_salary=base,
            allowance=float(payload.allowance or 0),
            overtime_hours=overtime_hours,
            overtime_rate=float(payload.overtime_rate or 0),
            overtime_amount=overtime_amount,
            deductions=float(payload.deductions or 0),
            gross=gross,
            pph21_method="ter",
            tax_pph21=tax,
            net_pay=gross - tax - float(payload.deductions or 0),
        )
        slips.append(slip)

    existing = {
        (s.run_id, s.employee_id) for s in db.execute(
            select(Payslip).where(Payslip.run_id == run.id)
        ).scalars()
    }
    added = [s for s in slips if (s.run_id, s.employee_id) not in existing]
    if not added:
        message = "Semua slip sudah ada"
        if skipped_unapproved:
            message += f"; {skipped_unapproved} lembur belum disetujui klien"
        raise HTTPException(status_code=409, detail=message)
    db.add_all(added)
    db.commit()
    for slip in added:
        db.refresh(slip)
    return added


def finalize_run(db: Session, run_id: str) -> PayrollRun:
    run = _get_run(db, run_id)
    if run.status == PayrollRunStatus.final:
        raise HTTPException(status_code=409, detail="Payroll run sudah final")
    if not run.slips:
        raise HTTPException(status_code=422, detail="Belum ada slip gaji untuk difinalisasi")
    run.status = PayrollRunStatus.final
    run.finalized_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run


# ---------- Preview pajak ----------


def preview_tax(payload: TaxPreviewIn) -> dict:
    profile = TaxProfile(marital_status=payload.marital_status, dependents=payload.dependents)
    if payload.method == "pasal17":
        tax = compute_pasal17_monthly_average(
            payload.gross_monthly, payload.months, profile
        )
    else:
        tax = compute_ter(payload.gross_monthly, profile)
    return {"tax_pph21": tax, "method": payload.method}
