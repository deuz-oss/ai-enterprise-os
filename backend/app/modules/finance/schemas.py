from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.finance.models import CashFlowDirection, InvoiceStatus


class InvoiceGenerateRequest(BaseModel):
    client_id: UUID
    year: int
    month: int
    fee_amount: float = 0
    ppn_rate: float | None = None  # None → pakai default konfigurasi
    pph23_rate: float | None = None
    notes: str | None = None
    # Payrol proyek dua jalur: tagih dari run tertentu (line-item Saltab)
    run_id: UUID | None = None

    @field_validator("month")
    @classmethod
    def _valid_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("Bulan harus 1-12")
        return v


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    invoice_no: str
    year: int
    month: int
    payroll_total: float
    fee_amount: float
    ppn_rate: float
    ppn_amount: float
    pph23_rate: float
    pph23_amount: float
    total_due: float
    status: InvoiceStatus
    issued_date: date | None
    due_date: date | None
    paid_at: datetime | None
    notes: str | None


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    due_date: date | None = None
    notes: str | None = None


class AgingRow(BaseModel):
    invoice_id: UUID
    invoice_no: str
    client_name: str
    total_due: float
    due_date: date
    days_overdue: int
    bucket: str


class CashFlowCreate(BaseModel):
    direction: CashFlowDirection
    category: str
    amount: float
    entry_date: date | None = None
    description: str | None = None
    invoice_id: UUID | None = None


class CashFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    direction: CashFlowDirection
    category: str
    amount: float
    entry_date: date
    description: str | None
    invoice_id: UUID | None


class CashFlowSummary(BaseModel):
    year: int
    month: int | None
    inflow: float
    outflow: float
    net: float
