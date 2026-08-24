from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import parse_uuid
from app.modules import audit
from app.modules.auth.models import User, UserRole
from app.modules.ess.models import LeaveBalance, LeaveRequest, LeaveStatus, LeaveType
from app.modules.ess.schemas import LeaveBalanceUpsertIn, LeaveCreate
from app.modules.hrd.models import Employee, EmployeeDocument, EmploymentContract
from app.modules.payroll.models import (
    AttendanceSummary,
    PayrollRun,
    PayrollRunStatus,
    Payslip,
)


def get_own_employee(db: Session, user) -> Employee:
    """Satu-satunya pintu data portal: karyawan tertaut ke akun login sendiri."""
    employee = db.execute(select(Employee).where(Employee.user_id == user.id)).scalar_one_or_none()
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Akun ini belum tertaut ke data karyawan; hubungi HR",
        )
    return employee


def list_contracts(db: Session, user) -> list[EmploymentContract]:
    return list(get_own_employee(db, user).contracts)


def list_documents(db: Session, user) -> list[EmployeeDocument]:
    return list(get_own_employee(db, user).documents)


def _get_own_document(db: Session, user, document_id: str) -> EmployeeDocument:
    document = db.get(EmployeeDocument, parse_uuid(document_id))
    if document is None or document.employee.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    return document


def _get_own_contract(db: Session, user, contract_id: str) -> EmploymentContract:
    contract = db.get(EmploymentContract, parse_uuid(contract_id))
    if contract is None or contract.employee.user_id != user.id:
        raise HTTPException(status_code=404, detail="Kontrak kerja tidak ditemukan")
    return contract


def document_download_url(db: Session, user, document_id: str) -> str:
    document = _get_own_document(db, user, document_id)
    audit.log_event(
        db,
        action="ess.document.download_url",
        entity_type="employee_document",
        entity_id=document.id,
        object_key=document.object_key,
        detail={"file_name": document.file_name},
    )
    return storage.presigned_get_url(document.object_key)


def contract_file_download_url(db: Session, user, contract_id: str) -> str:
    contract = _get_own_contract(db, user, contract_id)
    if not contract.object_key:
        raise HTTPException(status_code=404, detail="Kontrak belum punya file")
    audit.log_event(
        db,
        action="ess.contract.download_url",
        entity_type="employment_contract",
        entity_id=contract.id,
        object_key=contract.object_key,
        detail={"file_name": contract.file_name},
    )
    return storage.presigned_get_url(contract.object_key)


def list_payslips(db: Session, user) -> list[dict]:
    """Slip gaji sendiri dari payroll run final saja (draft belum boleh terlihat)."""
    own_id = get_own_employee(db, user).id
    rows = db.execute(
        select(Payslip, PayrollRun)
        .join(PayrollRun, Payslip.run_id == PayrollRun.id)
        .where(Payslip.employee_id == own_id)
        .where(PayrollRun.status == PayrollRunStatus.final)
        .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    ).all()
    return [
        {
            "id": slip.id,
            "year": run.year,
            "month": run.month,
            "base_salary": slip.base_salary,
            "allowance": slip.allowance,
            "overtime_hours": slip.overtime_hours,
            "overtime_amount": slip.overtime_amount,
            "deductions": slip.deductions,
            "gross": slip.gross,
            "pph21_method": slip.pph21_method,
            "tax_pph21": slip.tax_pph21,
            "net_pay": slip.net_pay,
        }
        for slip, run in rows
    ]


# ---------- Absensi sendiri ----------


def list_own_attendance(
    db: Session, user, year: int | None = None, month: int | None = None
) -> list[AttendanceSummary]:
    """Rekap kehadiran bulanan milik akun sendiri; tanpa parameter = semua periode."""
    stmt = (
        select(AttendanceSummary)
        .where(AttendanceSummary.employee_id == get_own_employee(db, user).id)
        .order_by(AttendanceSummary.year.desc(), AttendanceSummary.month.desc())
    )
    if year is not None:
        stmt = stmt.where(AttendanceSummary.year == year)
    if month is not None:
        stmt = stmt.where(AttendanceSummary.month == month)
    return list(db.execute(stmt).scalars())


# ---------- Pengajuan cuti/izin ----------


def _get_own_leave(db: Session, user, leave_id: str) -> LeaveRequest:
    leave = db.get(LeaveRequest, parse_uuid(leave_id))
    if leave is None or leave.employee.user_id != user.id:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    return leave


def create_leave_request(db: Session, user, payload: LeaveCreate) -> LeaveRequest:
    leave = LeaveRequest(
        employee_id=get_own_employee(db, user).id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=(payload.reason or "").strip() or None,
        status=LeaveStatus.pending,
    )
    overlapping = db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.employee_id == leave.employee_id)
        .where(LeaveRequest.status.in_([LeaveStatus.pending, LeaveStatus.approved]))
        .where(LeaveRequest.start_date <= leave.end_date)
        .where(LeaveRequest.end_date >= leave.start_date)
    ).scalar_one_or_none()
    if overlapping is not None:
        raise HTTPException(
            status_code=409,
            detail="Sudah ada pengajuan cuti/izin yang bertabrakan pada tanggal tersebut",
        )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    audit.log_event(
        db,
        action="leave.request_submitted",
        entity_type="leave_request",
        entity_id=leave.id,
        detail={
            "leave_type": leave.leave_type.value,
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
        },
    )
    return leave


def list_own_leave_requests(db: Session, user) -> list[LeaveRequest]:
    employee = get_own_employee(db, user)
    return list(
        db.execute(
            select(LeaveRequest)
            .where(LeaveRequest.employee_id == employee.id)
            # Tiebreaker start_date untuk pengajuan dalam detik yang sama.
            .order_by(LeaveRequest.created_at.desc(), LeaveRequest.start_date.desc())
        ).scalars()
    )


def cancel_own_leave_request(db: Session, user, leave_id: str) -> LeaveRequest:
    leave = _get_own_leave(db, user, leave_id)
    if leave.status != LeaveStatus.pending:
        raise HTTPException(
            status_code=409, detail="Hanya pengajuan berstatus menunggu yang bisa dibatalkan"
        )
    leave.status = LeaveStatus.cancelled
    db.commit()
    db.refresh(leave)
    audit.log_event(
        db,
        action="leave.cancelled",
        entity_type="leave_request",
        entity_id=leave.id,
    )
    return leave


# ---------- Cuti/izin sisi HR ----------


def hr_list_leave_requests(
    db: Session,
    status_filter: LeaveStatus | None = None,
    employee_id=None,
) -> list[LeaveRequest]:
    stmt = select(LeaveRequest).order_by(
        LeaveRequest.created_at.desc(), LeaveRequest.start_date.desc()
    )
    if status_filter is not None:
        stmt = stmt.where(LeaveRequest.status == status_filter)
    if employee_id is not None:
        stmt = stmt.where(LeaveRequest.employee_id == parse_uuid(str(employee_id)))
    return list(db.execute(stmt).scalars())


def decide_leave_request(
    db: Session, user, leave_id: str, approved: bool, note: str | None
) -> LeaveRequest:
    """HR menyetujui/menolak pengajuan yang masih pending.

    Approval cuti tahunan memotong jatah cuti bila kuota untuk tahun
    terkait sudah diatur; tanpa baris balance, approval tidak dibatasi.
    """
    leave = db.get(LeaveRequest, parse_uuid(leave_id))
    if leave is None:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=409, detail="Pengajuan sudah diputus sebelumnya")
    if approved and leave.leave_type == LeaveType.annual:
        _consume_balance(db, leave)
    leave.status = LeaveStatus.approved if approved else LeaveStatus.rejected
    leave.decided_by = user.id
    leave.decided_at = datetime.now(UTC)
    leave.decision_note = (note or "").strip() or None
    db.commit()
    db.refresh(leave)
    audit.log_event(
        db,
        action="leave.decided",
        entity_type="leave_request",
        entity_id=leave.id,
        detail={"approved": approved, "status": leave.status.value},
    )
    return leave


def _consume_balance(db: Session, leave: LeaveRequest) -> None:
    """Validasi & potong jatah cuti tahunan (dipanggil sebelum status berubah)."""
    days = (leave.end_date - leave.start_date).days + 1
    balance = _balance_for(db, leave.employee_id, leave.start_date.year)
    if balance is None:
        return  # kuota belum diatur HR → tidak dibatasi
    if balance.used_days + days > balance.total_days:
        sisa = balance.total_days - balance.used_days
        raise HTTPException(
            status_code=422,
            detail=(f"Jatah cuti {balance.year} tidak cukup: butuh {days} hari, sisa {sisa} hari"),
        )
    balance.used_days += days


# ---------- Jatah cuti ----------


def _balance_for(db: Session, employee_id, year: int) -> LeaveBalance | None:
    return db.execute(
        select(LeaveBalance)
        .where(LeaveBalance.employee_id == parse_uuid(str(employee_id)))
        .where(LeaveBalance.year == year)
    ).scalar_one_or_none()


def upsert_leave_balance(
    db: Session, employee_id: str, payload: LeaveBalanceUpsertIn
) -> LeaveBalance:
    """HR membuat/memperbarui jatah cuti tahunan; used_days tidak direset."""
    from app.modules.hrd.models import Employee

    employee = db.get(Employee, parse_uuid(employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    balance = _balance_for(db, employee.id, payload.year)
    if balance is None:
        balance = LeaveBalance(
            employee_id=employee.id, year=payload.year, total_days=payload.total_days
        )
        db.add(balance)
    else:
        if payload.total_days < balance.used_days:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Jatah baru lebih kecil dari yang sudah terpakai ({balance.used_days} hari)"
                ),
            )
        balance.total_days = payload.total_days
    db.commit()
    db.refresh(balance)
    audit.log_event(
        db,
        action="leave.balance_upserted",
        entity_type="leave_balance",
        entity_id=balance.id,
        detail={
            "employee_id": str(employee.id),
            "year": balance.year,
            "total_days": balance.total_days,
        },
    )
    return balance


def get_employee_leave_balance(db: Session, employee_id: str, year: int) -> LeaveBalance | None:
    from app.modules.hrd.models import Employee

    employee = db.get(Employee, parse_uuid(employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return _balance_for(db, employee.id, year)


def get_own_leave_balance(db: Session, user, year: int | None) -> LeaveBalance | None:
    """Jatah cuti milik akun sendiri; default tahun berjalan. Null = belum diatur."""
    own_id = get_own_employee(db, user).id
    effective_year = year or datetime.now(UTC).year
    return _balance_for(db, own_id, effective_year)


def list_selfservice_accounts(db: Session) -> list[User]:
    """Akun role karyawan bertenanta aktif yang belum tertaut ke karyawan mana pun."""
    from app.core.tenancy import get_tenant

    tenant_id = get_tenant()
    if tenant_id is None:
        return []
    stmt = (
        select(User)
        .outerjoin(Employee, Employee.user_id == User.id)
        .where(User.role == UserRole.employee)
        .where(User.tenant_id == tenant_id)
        .where(User.is_active.is_(True))
        .where(Employee.id.is_(None))
        .order_by(User.email)
    )
    return list(db.execute(stmt).scalars())
