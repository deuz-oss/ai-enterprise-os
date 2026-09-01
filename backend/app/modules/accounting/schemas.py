from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.modules.accounting.models import GroupType, JournalEntryStatus


class JournalLineIn(BaseModel):
    account_code: str
    debit: float = 0
    credit: float = 0
    client_dim_id: UUID | None = None
    memo: str | None = None

    @model_validator(mode="after")
    def _one_side_only(self) -> "JournalLineIn":
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Isi debit ATAU kredit (salah satu > 0), bukan keduanya/keduanya nol")
        return self


class JournalEntryIn(BaseModel):
    entry_date: date | None = None
    description: str
    reference: str | None = None
    status: str = "posted"  # posted | memorial (opt-in alur dua langkah)
    lines: list[JournalLineIn]

    @field_validator("lines")
    @classmethod
    def _at_least_two_lines(cls, v: list[JournalLineIn]) -> list[JournalLineIn]:
        if len(v) < 2:
            raise ValueError("Jurnal minimal punya 2 baris (debit & kredit)")
        return v

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ("posted", "memorial"):
            raise ValueError("Status harus 'posted' atau 'memorial'")
        return v

    @model_validator(mode="after")
    def _balanced(self) -> "JournalEntryIn":
        # Jurnal memorial boleh tidak seimbang saat penyusunan;
        # validasi keseimbangan dilakukan saat POSTING.
        if self.status == "memorial":
            return self
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(f"Jurnal tidak seimbang: debit {total_debit} != kredit {total_credit}")
        return self


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_code: str
    debit: float
    credit: float
    client_dim_id: UUID | None
    memo: str | None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_date: date
    description: str
    reference: str | None
    status: JournalEntryStatus
    event_code: str | None = None
    source_ref_type: str | None = None
    source_ref_id: UUID | None = None
    lines: list[JournalLineOut]
    # Turunan (bukan kolom fisik) — dihitung dari baris `event_code=journal_reversed`
    # yang menunjuk balik ke entry ini. Default aman untuk entry yang baru
    # dibuat/diposting/dibalik (belum mungkin sudah punya reversal sendiri).
    is_reversed: bool = False
    reversal_entry_id: UUID | None = None


class JournalReverseIn(BaseModel):
    reversal_date: date | None = None
    reason: str | None = None


class TrialBalanceRow(BaseModel):
    account_code: str
    account_name: str
    category: str
    total_debit: float
    total_credit: float


class IncomeStatementRow(BaseModel):
    account_code: str
    account_name: str
    amount: float


class IncomeStatement(BaseModel):
    year: int
    revenues: list[IncomeStatementRow]
    expenses: list[IncomeStatementRow]
    total_revenue: float
    total_expense: float
    net_income: float


class BalanceSheetSection(BaseModel):
    rows: list[IncomeStatementRow]
    total: float


class BalanceSheet(BaseModel):
    as_of: date
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    net_income: float


# ---------- Fase 10: COA dinamis & periode ----------


class AccountCreate(BaseModel):
    code: str
    name: str
    parent_code: str | None = None
    group_type: GroupType
    normal_balance: str = "debit"
    is_cash_bank: bool = False
    is_control_ar_ap: bool = False

    @field_validator("normal_balance")
    @classmethod
    def _valid_normal(cls, v: str) -> str:
        if v not in ("debit", "kredit"):
            raise ValueError("Saldo normal harus debit atau kredit")
        return v


class AccountUpdate(BaseModel):
    name: str | None = None
    group_type: GroupType | None = None
    is_active: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    parent_code: str | None
    group_type: GroupType
    normal_balance: str
    is_cash_bank: bool
    is_control_ar_ap: bool
    is_active: bool


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int
    closed_at: datetime | None
    notes: str | None
