from datetime import date
from typing import Any

from pydantic import BaseModel


class Pph21ConfigCreate(BaseModel):
    effective_from: date
    ptkp_diri: float = 54_000_000
    ptkp_kawin: float = 4_500_000
    ptkp_tanggungan: float = 4_500_000
    max_tanggungan: int = 3
    pasal17_brackets: Any  # list of [upper, rate], null for inf
    ter_a: Any
    ter_b: Any
    ter_c: Any


class Pph21ConfigOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    effective_from: date
    ptkp_diri: float
    ptkp_kawin: float
    ptkp_tanggungan: float
    max_tanggungan: int
    pasal17_brackets: Any
    ter_a: Any
    ter_b: Any
    ter_c: Any


class BpjsConfigCreate(BaseModel):
    effective_from: date
    kesehatan_employer: float = 0.04
    kesehatan_employee: float = 0.01
    kesehatan_cap: float = 12_000_000
    jht_employer: float = 0.037
    jht_employee: float = 0.02
    jp_employer: float = 0.02
    jp_employee: float = 0.01
    jp_cap: float = 10_547_400
    jkm_rate: float = 0.003
    jkk_rates: Any
    default_jkk_category: int = 2


class BpjsConfigOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    effective_from: date
    kesehatan_employer: float
    kesehatan_employee: float
    kesehatan_cap: float
    jht_employer: float
    jht_employee: float
    jp_employer: float
    jp_employee: float
    jp_cap: float
    jkm_rate: float
    jkk_rates: Any
    default_jkk_category: int


class BillingTaxConfigCreate(BaseModel):
    effective_from: date
    ppn_rate: float = 0.11
    pph23_rate: float = 0.02
    due_days: int = 30


class BillingTaxConfigOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    effective_from: date
    ppn_rate: float
    pph23_rate: float
    due_days: int


class BankFeeCreate(BaseModel):
    bank_name: str
    fee: float = 3500
    is_mandiri_group: bool = False


class BankFeeOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    bank_name: str
    fee: float
    is_mandiri_group: bool
