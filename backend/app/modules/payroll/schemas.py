from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.payroll.models import PayrollRunStatus


class AttendanceUpsert(BaseModel):
    employee_id: UUID
    year: int
    month: int
    present_days: int = 0
    overtime_hours: int = 0
    notes: str | None = None

    @field_validator("month")
    @classmethod
    def _valid_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("Bulan harus 1-12")
        return v


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    year: int
    month: int
    present_days: int
    overtime_hours: int
    client_approved: bool
    approved_at: datetime | None
    notes: str | None


class RunCreate(BaseModel):
    year: int
    month: int

    @field_validator("month")
    @classmethod
    def _valid_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("Bulan harus 1-12")
        return v


class GenerateSlipsRequest(BaseModel):
    """Kosong = semua karyawan aktif; isi daftar untuk subset karyawan."""

    employee_ids: list[UUID] | None = None
    allowance: float = 0
    deductions: float = 0
    overtime_rate: float = 0


class PayslipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    employee_id: UUID
    base_salary: float
    allowance: float
    overtime_hours: int
    overtime_rate: float
    overtime_amount: float
    deductions: float
    gross: float
    pph21_method: str
    tax_pph21: float
    net_pay: float


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    month: int
    status: PayrollRunStatus
    finalized_at: datetime | None
    created_at: datetime


class TaxPreviewIn(BaseModel):
    gross_monthly: float
    marital_status: str = "tk"
    dependents: int = 0
    method: str = "ter"  # "ter" atau "pasal17"
    months: int = 1
