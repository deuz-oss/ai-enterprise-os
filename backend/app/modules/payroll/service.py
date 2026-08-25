import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules.hrd.models import Employee, EmployeeStatus
from app.modules.payroll.models import (
    AttendanceSummary,
    PayrollRun,
    PayrollRunStatus,
    PayrollRunToken,
    PayrollRunType,
    Payslip,
)
from app.modules.payroll.schemas import (
    AttendanceUpsert,
    GenerateSlipsRequest,
    RunCreate,
    TaxPreviewIn,
)
from app.modules.payroll.tax import TaxProfile, compute_pasal17_monthly_average, compute_ter
from app.modules.rates.service import get_effective_bpjs, get_effective_pph21

# Transisi status yang diizinkan per jenis payrol (ADR-0006 / PRD Fase 9).
_ALLOWED_TRANSITIONS: dict[PayrollRunType, dict[PayrollRunStatus, set[PayrollRunStatus]]] = {
    PayrollRunType.internal: {
        PayrollRunStatus.draft: {PayrollRunStatus.finance_processing, PayrollRunStatus.final},
        PayrollRunStatus.finance_processing: {PayrollRunStatus.final},
    },
    PayrollRunType.proyek: {
        PayrollRunStatus.draft: {PayrollRunStatus.submitted_to_client},
        PayrollRunStatus.client_rejected: {PayrollRunStatus.submitted_to_client},
        # Diputuskan klien hanya lewat link ber-token (decide_by_token).
        PayrollRunStatus.submitted_to_client: {
            PayrollRunStatus.client_approved,
            PayrollRunStatus.client_rejected,
        },
        PayrollRunStatus.client_approved: {PayrollRunStatus.finance_processing},
        PayrollRunStatus.finance_processing: {PayrollRunStatus.final},
    },
}

# Status saat slip masih boleh dibuat/diperbarui.
_EDITABLE_STATUSES: dict[PayrollRunType, set[PayrollRunStatus]] = {
    PayrollRunType.internal: {PayrollRunStatus.draft},
    PayrollRunType.proyek: {PayrollRunStatus.draft, PayrollRunStatus.client_rejected},
}


def _assert_run_license(db: Session, tenant_id, run_type: PayrollRunType) -> None:
    """Guard lisensi data-driven (ADR-0006): mutasi mengikuti run_type."""
    from app.modules.platform.service import is_licensed

    key = "hr_payroll" if run_type == PayrollRunType.internal else "operations_billing"
    if not is_licensed(db, tenant_id, key):
        label = "HR & Payroll" if key == "hr_payroll" else "Operations & Billing"
        raise HTTPException(
            status_code=403,
            detail=f"Aplikasi {label} belum aktif untuk perusahaan Anda.",
        )


def _transition(run: PayrollRun, target: PayrollRunStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS[run.run_type].get(run.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Perubahan status {run.status.value} → {target.value} tidak diizinkan",
        )
    run.status = target


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
    # Validasi dua jalur (Fase 8): approval klien hanya untuk karyawan eksternal.
    if summary.employee.employment_type.value != "eksternal":
        raise HTTPException(
            status_code=422,
            detail="Karyawan internal divalidasi oleh HR (jalur /attendance/summaries)",
        )
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


def create_run(db: Session, payload: RunCreate, tenant_id=None) -> PayrollRun:
    _assert_run_license(db, tenant_id, payload.run_type)
    if payload.run_type == PayrollRunType.proyek and payload.client_id is not None:
        from app.modules.clients.models import Client

        if db.get(Client, payload.client_id) is None:
            raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    duplicate = db.execute(
        select(PayrollRun).where(
            PayrollRun.year == payload.year,
            PayrollRun.month == payload.month,
            PayrollRun.run_type == payload.run_type,
            PayrollRun.client_id == payload.client_id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        label = f"payrol {payload.run_type.value}"
        if payload.client_id:
            from app.modules.clients.models import Client

            client = db.get(Client, payload.client_id)
            label += f" klien {client.name}" if client else ""
        raise HTTPException(
            status_code=409,
            detail=f"{label.capitalize()} periode {payload.year}-{payload.month} sudah ada",
        )
    run = PayrollRun(
        year=payload.year,
        month=payload.month,
        run_type=payload.run_type,
        client_id=payload.client_id,
    )
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


def generate_slips(
    db: Session, run_id: str, payload: GenerateSlipsRequest, tenant_id=None
) -> list[Payslip]:
    """Buat slip gaji untuk karyawan aktif; hanya lembur yang disetujui klien."""
    run = _get_run(db, run_id)
    _assert_run_license(db, tenant_id, run.run_type)
    if run.status not in _EDITABLE_STATUSES[run.run_type]:
        raise HTTPException(
            status_code=409,
            detail=(
                "Slip hanya bisa dibuat saat status draft "
                "(atau ditolak klien untuk payrol proyek)"
            ),
        )

    # Resolve rate ber-versi untuk periode ini; snapshot disimpan di run untuk historis.
    period_date = date(run.year, run.month, 1)
    pph21_cfg = get_effective_pph21(db, period_date)
    bpjs_cfg = get_effective_bpjs(db, period_date)
    # Simpan snapshot JSON agar laporan historis tetap konsisten walau rate diperbarui
    if pph21_cfg and run.pph21_snapshot is None:
        run.pph21_snapshot = {
            "effective_from": pph21_cfg.effective_from.isoformat(),
            "ptkp_diri": float(pph21_cfg.ptkp_diri),
            "config_id": pph21_cfg.id,
        }
    if bpjs_cfg and run.bpjs_snapshot is None:
        run.bpjs_snapshot = {
            "effective_from": bpjs_cfg.effective_from.isoformat(),
            "config_id": bpjs_cfg.id,
        }

    employee_stmt = select(Employee).where(Employee.status == EmployeeStatus.active)
    if payload.employee_ids:
        ids = [parse_uuid(str(e)) for e in payload.employee_ids]
        employee_stmt = employee_stmt.where(Employee.id.in_(ids))
    # Payrol proyek: hanya karyawan yang ditempatkan di klien run ini.
    if run.run_type == PayrollRunType.proyek and run.client_id is not None:
        from app.modules.clients.models import Client  # noqa: F401
        from app.modules.recruitment.models import JobOrder, Placement

        employee_stmt = (
            employee_stmt.join(Placement, Employee.placement_id == Placement.id)
            .join(JobOrder, Placement.job_order_id == JobOrder.id)
            .where(JobOrder.client_id == run.client_id)
        )
    employees = list(db.execute(employee_stmt).scalars())
    if not employees:
        detail = "Tidak ada karyawan aktif untuk diproses"
        if run.run_type == PayrollRunType.proyek:
            detail = "Tidak ada karyawan aktif yang ditempatkan di klien ini"
        raise HTTPException(status_code=422, detail=detail)

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

        # Gunakan config ber-versi jika ada, fallback ke konstanta kode
        period_date = date(run.year, run.month, 1)
        profile = TaxProfile.from_db(
            db,
            period_date,
            marital_status=(employee.marital_status.value if employee.marital_status else "tk"),
            dependents=employee.dependents or 0,
        )
        tax = compute_ter(gross, profile)
        # Potongan admin bank otomatis (non-Mandiri) dari config
        try:
            from app.modules.rates.service import get_bank_fee

            bank_fee = get_bank_fee(db, employee.bank_name or "")
        except Exception:
            bank_fee = 0

        total_deductions = float(payload.deductions or 0) + bank_fee
        slip = Payslip(
            run_id=run.id,
            employee_id=employee.id,
            base_salary=base,
            allowance=float(payload.allowance or 0),
            overtime_hours=overtime_hours,
            overtime_rate=float(payload.overtime_rate or 0),
            overtime_amount=overtime_amount,
            deductions=total_deductions,
            gross=gross,
            pph21_method="ter",
            tax_pph21=tax,
            net_pay=gross - tax - total_deductions,
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


def finalize_run(db: Session, run_id: str, tenant_id=None) -> PayrollRun:
    run = _get_run(db, run_id)
    _assert_run_license(db, tenant_id, run.run_type)
    if not run.slips:
        raise HTTPException(status_code=422, detail="Belum ada slip gaji untuk difinalisasi")
    _transition(run, PayrollRunStatus.final)
    run.finalized_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    from app.modules import audit

    audit.log_event(
        db,
        action="payroll.finalized",
        entity_type="payroll_run",
        entity_id=run.id,
        detail={"run_type": run.run_type.value, "period": f"{run.year}-{run.month:02d}"},
    )
    return run


# ---------- Alur approval klien (link ber-token) ----------


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def submit_to_client(
    db: Session, tenant_id, run_id: str, days: int = 14
) -> tuple[PayrollRun, str, datetime]:
    """Kirim payrol proyek ke klien: status berubah + buat link ber-token."""
    run = _get_run(db, run_id)
    _assert_run_license(db, tenant_id, run.run_type)
    if run.run_type != PayrollRunType.proyek:
        raise HTTPException(
            status_code=422,
            detail=(
                "Hanya payrol proyek yang dikirim ke klien; "
                "payrol internal langsung diproses Finance"
            ),
        )
    if not 1 <= days <= 90:
        raise HTTPException(status_code=422, detail="Masa berlaku token 1-90 hari")
    if not run.slips:
        raise HTTPException(status_code=422, detail="Belum ada slip gaji untuk dikirim ke klien")

    # Cabut token lama yang belum terpakai.
    for stale in db.execute(
        select(PayrollRunToken).where(
            PayrollRunToken.run_id == run.id, PayrollRunToken.decided_at.is_(None)
        )
    ).scalars():
        db.delete(stale)

    raw = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(days=days)
    db.add(
        PayrollRunToken(
            run_id=run.id,
            token_hash=_hash_token(raw),
            expires_at=expires_at,
        )
    )
    _transition(run, PayrollRunStatus.submitted_to_client)
    db.commit()
    db.refresh(run)
    from app.modules import audit

    audit.log_event(
        db,
        action="payroll.submitted_to_client",
        entity_type="payroll_run",
        entity_id=run.id,
        detail={"expires_days": days, "slips": len(run.slips)},
    )
    return run, raw, expires_at


def _find_token(db: Session, raw_token: str) -> PayrollRunToken:
    token = db.execute(
        select(PayrollRunToken).where(PayrollRunToken.token_hash == _hash_token(raw_token))
    ).scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=404, detail="Link approval tidak valid")
    if token.decided_at is not None:
        raise HTTPException(status_code=409, detail="Keputusan untuk link ini sudah direkam")
    expires = token.expires_at
    now = datetime.now(UTC)
    if expires.tzinfo is None:
        now = now.replace(tzinfo=None)
    if expires < now:
        raise HTTPException(status_code=410, detail="Link approval sudah kedaluwarsa")
    return token


def client_view(db: Session, raw_token: str) -> dict:
    """Ringkasan Saltab read-only untuk link approval klien (tanpa akun)."""
    token = _find_token(db, raw_token)
    run = db.get(PayrollRun, token.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payrol tidak ditemukan")
    lines = [
        {
            "employee_name": s.employee.full_name,
            "base_salary": float(s.base_salary),
            "allowance": float(s.allowance),
            "overtime_amount": float(s.overtime_amount),
            "deductions": float(s.deductions),
            "gross": float(s.gross),
            "tax_pph21": float(s.tax_pph21),
            "net_pay": float(s.net_pay),
        }
        for s in run.slips
    ]
    return {
        "client": run.client.name if run.client else None,
        "year": run.year,
        "month": run.month,
        "status": run.status.value,
        "expires_at": token.expires_at,
        "decided": token.decided_at is not None,
        "decided_by_name": token.decided_by_name,
        "decision_note": token.decision_note,
        "lines": lines,
        "total_net_pay": sum(line["net_pay"] for line in lines),
        "total_gross": sum(line["gross"] for line in lines),
    }


def decide_by_token(
    db: Session, raw_token: str, approved: bool, name: str, note: str | None
) -> dict:
    """Rekam keputusan klien dari link publik; transisi status divalidasi."""
    token = _find_token(db, raw_token)
    run = db.get(PayrollRun, token.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payrol tidak ditemukan")

    target = (
        PayrollRunStatus.client_approved if approved else PayrollRunStatus.client_rejected
    )
    _transition(run, target)
    token.decided_at = datetime.now(UTC)
    token.decided_by_name = name[:255]
    token.decision_note = (note or "").strip()[:500] or None
    db.commit()
    db.refresh(run)

    from app.modules import audit
    from app.modules.notifications.service import notify_hr_users

    audit.log_event(
        db,
        action="payroll.client_decision",
        entity_type="payroll_run",
        entity_id=run.id,
        detail={"approved": approved, "by": name},
    )
    keputusan = "disetujui" if approved else "ditolak"
    notify_hr_users(
        db,
        title=f"Payrol proyek {run.month}/{run.year}: {keputusan} klien",
        body=(f"Keputusan oleh {name}" + (f" — {note}" if note else "")),
        entity_id=run.id,
    )
    return {
        "status": run.status.value,
        "decided_by_name": token.decided_by_name,
        "decision_note": token.decision_note,
    }


def start_finance_processing(db: Session, run_id: str, tenant_id=None) -> PayrollRun:
    run = _get_run(db, run_id)
    _assert_run_license(db, tenant_id, run.run_type)
    _transition(run, PayrollRunStatus.finance_processing)
    db.commit()
    db.refresh(run)
    from app.modules import audit

    audit.log_event(
        db,
        action="payroll.finance_processing",
        entity_type="payroll_run",
        entity_id=run.id,
        detail={"run_type": run.run_type.value},
    )
    return run


def resubmit_allowed(run: PayrollRun) -> bool:
    """Setelah ditolak klien, angka boleh diperbaiki lalu dikirim ulang."""
    return run.status == PayrollRunStatus.client_rejected


# ---------- Preview pajak ----------


def preview_tax(payload: TaxPreviewIn, db: Session | None = None) -> dict:
    # Gunakan config ber-versi jika db tersedia
    effective = date.today()
    if db is not None:
        profile = TaxProfile.from_db(db, effective, payload.marital_status, payload.dependents)
    else:
        profile = TaxProfile(marital_status=payload.marital_status, dependents=payload.dependents)
    if payload.method == "pasal17":
        tax = compute_pasal17_monthly_average(
            payload.gross_monthly, payload.months, profile
        )
    else:
        tax = compute_ter(payload.gross_monthly, profile)
    return {"tax_pph21": tax, "method": payload.method}
