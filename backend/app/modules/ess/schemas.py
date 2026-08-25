from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

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
    file_name: str | None
    file_size: int
    created_at: datetime


class SelfserviceAccountOut(BaseModel):
    """Akun role karyawan yang belum tertaut ke data karyawan mana pun."""

    id: UUID
    email: str
    full_name: str


class LeaveDecisionIn(BaseModel):
    approved: bool
    note: str | None = None


class AttendanceCorrectionCreate(BaseModel):
    year: int
    month: int
    requested_present_days: int = 0
    requested_overtime_hours: int = 0
    reason: str | None = None

    @field_validator("year")
    @classmethod
    def _sane_year(cls, v: int) -> int:
        if not 2000 <= v <= 2100:
            raise ValueError("Tahun tidak wajar")
        return v

    @field_validator("month")
    @classmethod
    def _valid_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("Bulan harus 1-12")
        return v

    @field_validator("requested_present_days", "requested_overtime_hours")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Angka tidak boleh negatif")
        return v


class AttendanceCorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    year: int
    month: int
    requested_present_days: int
    requested_overtime_hours: int
    reason: str | None
    status: LeaveStatus
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime


class LeaveBalanceUpsertIn(BaseModel):
    """HR mengatur jatah cuti tahunan karyawan untuk satu periode."""

    year: int
    total_days: int

    @field_validator("year")
    @classmethod
    def _sane_year(cls, v: int) -> int:
        if not 2000 <= v <= 2100:
            raise ValueError("Tahun tidak wajar")
        return v

    @field_validator("total_days")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Jatah cuti tidak boleh negatif")
        return v


class LeaveBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    year: int
    total_days: int
    used_days: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def remaining(self) -> int:
        return self.total_days - self.used_days
