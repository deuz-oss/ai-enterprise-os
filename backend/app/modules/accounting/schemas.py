from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class JournalLineIn(BaseModel):
    account_code: str
    debit: float = 0
    credit: float = 0

    @model_validator(mode="after")
    def _one_side_only(self) -> "JournalLineIn":
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Isi debit ATAU kredit (salah satu > 0), bukan keduanya/keduanya nol")
        return self


class JournalEntryIn(BaseModel):
    entry_date: date | None = None
    description: str
    reference: str | None = None
    lines: list[JournalLineIn]

    @field_validator("lines")
    @classmethod
    def _at_least_two_lines(cls, v: list[JournalLineIn]) -> list[JournalLineIn]:
        if len(v) < 2:
            raise ValueError("Jurnal minimal punya 2 baris (debit & kredit)")
        return v

    @model_validator(mode="after")
    def _balanced(self) -> "JournalEntryIn":
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(
                f"Jurnal tidak seimbang: debit {total_debit} != kredit {total_credit}"
            )
        return self


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_code: str
    debit: float
    credit: float


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_date: date
    description: str
    reference: str | None
    lines: list[JournalLineOut]


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
