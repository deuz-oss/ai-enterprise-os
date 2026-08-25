from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.payroll.models import PayrollRunStatus, PayrollRunType


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
    run_type: PayrollRunType = PayrollRunType.internal
    client_id: UUID | None = None

    @field_validator("month")
    @classmethod
    def _valid_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("Bulan harus 1-12")
        return v

    @model_validator(mode="after")
    def _proyek_needs_client(self) -> "RunCreate":
        if self.run_type == PayrollRunType.proyek and self.client_id is None:
            raise ValueError("Payrol proyek wajib memilih klien")
        if self.run_type == PayrollRunType.internal:
            self.client_id = None
        return self


class GenerateSlipsRequest(BaseModel):
    """Kosong = semua karyawan aktif; isi daftar untuk subset karyawan.

    Fase 9b (opsional, default nonaktif demi kompatibilitas):
    - prorata_absensi: gaji pokok & tunjangan diprorata dari hari hadir
      rekap tervalidasi ÷ hari kerja (Sen–Jum) bulan tersebut.
    - bpjs_enabled: potongan BPJS karyawan + passthrough BPJS perusahaan
      dihitung mesin BPJS dan menjadi line-item Saltab.
    """

    employee_ids: list[UUID] | None = None
    allowance: float = 0
    deductions: float = 0
    overtime_rate: float = 0
    prorata_absensi: bool = False
    bpjs_enabled: bool = False


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
    run_type: PayrollRunType
    client_id: UUID | None
    status: PayrollRunStatus
    finalized_at: datetime | None
    created_at: datetime


class ClientLinkCreate(BaseModel):
    days: int = 14  # masa berlaku token, 1–90 hari


class ClientDecisionIn(BaseModel):
    approved: bool
    name: str = Field(min_length=1, max_length=255)
    note: str | None = None


class TaxPreviewIn(BaseModel):
    gross_monthly: float
    marital_status: str = "tk"
    dependents: int = 0
    method: str = "ter"  # "ter" atau "pasal17"
    months: int = 1


# ---------- Saltab ----------


class SaltabComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ctype: str
    code: str
    name: str
    amount: float
    source: str
    notes: str | None


class SaltabRowOut(BaseModel):
    payslip_id: UUID
    employee_name: str
    status_run: str
    components: list[SaltabComponentOut]
    total_earnings: float
    total_deductions: float
    total_passthrough: float


class SaltabComponentUpdate(BaseModel):
    amount: float

    @field_validator("amount")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Nominal komponen tidak boleh negatif")
        return v
