from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class BankTxCreate(BaseModel):
    tx_type: str  # penerimaan | pembayaran | transfer_antar_rekening
    bank_account_id: str
    amount: float
    tx_date: date | None = None
    counter_account_id: str | None = None
    description: str | None = None


class BankTxOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    tx_date: date
    tx_type: str
    bank_account_id: UUID
    counter_account_id: UUID | None
    amount: float
    description: str | None
    reconciled_at: Any | None = None


class PurchaseBillCreate(BaseModel):
    vendor_name: str
    expense_account_id: str
    amount: float
    ppn_rate: float = 0
    entry_date: date | None = None
    due_date: date | None = None
    bill_number: str | None = None
    notes: str | None = None


class PurchaseBillOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    vendor_name: str
    bill_number: str | None
    amount: float
    ppn_rate: float
    ppn_amount: float
    entry_date: date
    due_date: date | None
    status: str
    notes: str | None


class FixedAssetCreate(BaseModel):
    name: str
    asset_account_id: str
    funding_account_id: str | None = None
    acquisition_date: date | None = None
    cost: float
    useful_life_months: int = 48
    notes: str | None = None

    @field_validator("cost")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Harga perolehan harus > 0")
        return v


class FixedAssetOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    acquisition_date: date
    cost: float
    useful_life_months: int
    accumulated_depreciation: float
    monthly_depreciation: float
    book_value: float
    last_depreciated_ym: str | None
    disposed_at: date | None


class APAgingRow(BaseModel):
    bill_id: UUID
    bill_number: str | None
    vendor_name: str
    total_due: float
    due_date: date
    days_overdue: int
    bucket: str  # "1-30" | "31-60" | ">60"
