from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.ess.models import LeaveStatus, LeaveType
from app.modules.hrd.models import EmployeeStatus, MaritalStatus


class ProfileOut(BaseModel):
    """Data pribadi karyawan untuk portal self-service (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_no: str
    full_name: str
    ktp_no: str | None
    npwp_no: str | None
    bpjs_kesehatan_no: str | None
    bpjs_ketenagakerjaan_no: str | None
    phone: str | None
    address: str | None
    bank_name: str | None
    bank_account: str | None
    join_date: date | None
    marital_status: MaritalStatus | None
    dependents: int
    status: EmployeeStatus


class MyPayslipOut(BaseModel):
    """Ringkasan slip gaji milik akun sendiri; hanya dari payroll run final."""

    id: UUID
    year: int
    month: int
    base_salary: float
    allowance: float
    overtime_hours: int
    overtime_amount: float
    deductions: float
    gross: float
    pph21_method: str
    tax_pph21: float
    net_pay: float


class MyAttendanceOut(BaseModel):
    """Rekap kehadiran bulanan milik akun sendiri (read-only)."""

    id: UUID
    year: int
    month: int
    present_days: int
    overtime_hours: int
    client_approved: bool
    notes: str | None


class LeaveCreate(BaseModel):
    leave_type: LeaveType = LeaveType.annual
    start_date: date
    end_date: date
    reason: str | None = None

    @field_validator("end_date")
    @classmethod
    def _end_not_before_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("Tanggal selesai sebelum tanggal mulai")
        return v


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str | None
    status: LeaveStatus
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime


class SelfserviceAccountOut(BaseModel):
    """Akun role karyawan yang belum tertaut ke data karyawan mana pun."""

    id: UUID
    email: str
    full_name: str


class LeaveDecisionIn(BaseModel):
    approved: bool
    note: str | None = None
