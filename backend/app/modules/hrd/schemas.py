import json
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.hrd.models import (
    ContractSignStatus,
    EmployeeStatus,
    EmploymentType,
    HrDocumentType,
    MaritalStatus,
    MovementType,
    WarningLetterType,
)


class EmployeeCreate(BaseModel):
    full_name: str
    employee_no: str | None = None
    placement_id: UUID | None = None
    ktp_no: str | None = None
    npwp_no: str | None = None
    bpjs_kesehatan_no: str | None = None
    bpjs_ketenagakerjaan_no: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    join_date: date | None = None
    marital_status: MaritalStatus | None = None
    dependents: int = 0
    base_salary: float = 0
    jkk_risk_category: int | None = None
    employment_type: EmploymentType = EmploymentType.eksternal
    grade: str | None = None
    level: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relation: str | None = None
    emergency_contact_phone: str | None = None
    citizen_address: dict = {}
    residential_address: dict = {}


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    employee_no: str | None = None
    ktp_no: str | None = None
    npwp_no: str | None = None
    bpjs_kesehatan_no: str | None = None
    bpjs_ketenagakerjaan_no: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    join_date: date | None = None
    status: EmployeeStatus | None = None
    marital_status: MaritalStatus | None = None
    dependents: int | None = None
    base_salary: float | None = None
    jkk_risk_category: int | None = None
    employment_type: EmploymentType | None = None
    # Taut/lepas akun login self-service (role karyawan); null = lepas tautan.
    user_id: UUID | None = None
    bpjs_kesehatan_status: str | None = None
    bpjs_ketenagakerjaan_status: str | None = None
    bpjs_kesehatan_valid_until: date | None = None
    bpjs_ketenagakerjaan_valid_until: date | None = None
    grade: str | None = None
    level: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relation: str | None = None
    emergency_contact_phone: str | None = None
    citizen_address: dict | None = None
    residential_address: dict | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_no: str
    full_name: str
    placement_id: UUID | None
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
    base_salary: float
    jkk_risk_category: int | None
    employment_type: EmploymentType
    user_id: UUID | None
    status: EmployeeStatus
    bpjs_kesehatan_status: str | None = None
    bpjs_ketenagakerjaan_status: str | None = None
    bpjs_kesehatan_valid_until: date | None = None
    bpjs_ketenagakerjaan_valid_until: date | None = None
    bpjs_kesehatan_card_key: str | None = None
    bpjs_ketenagakerjaan_card_key: str | None = None
    grade: str | None = None
    level: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relation: str | None = None
    emergency_contact_phone: str | None = None
    citizen_address: dict = {}
    residential_address: dict = {}
    payroll_locked: bool = False
    payroll_locked_at: datetime | None = None
    referral_code: str | None = None
    created_at: datetime
    updated_at: datetime


class InsuranceCreate(BaseModel):
    provider: str = "lainnya"
    policy_no: str
    status: str = "aktif"
    start_date: date | None = None
    valid_until: date | None = None


class InsuranceUpdate(BaseModel):
    provider: str | None = None
    policy_no: str | None = None
    status: str | None = None
    start_date: date | None = None
    valid_until: date | None = None


class InsuranceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    provider: str
    policy_no: str
    status: str
    start_date: date | None
    valid_until: date | None
    card_object_key: str | None
    policy_object_key: str | None
    uploaded_by: UUID | None
    uploaded_at: datetime
    created_at: datetime


class OnboardCreate(BaseModel):
    """Data minimum saat mengangkat kandidat yang sudah diterima klien."""

    placement_id: UUID
    employee_no: str | None = None
    join_date: date | None = None
    phone: str | None = None


class ContractCreate(BaseModel):
    contract_no: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class ContractUpdate(BaseModel):
    contract_no: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    sign_status: ContractSignStatus | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    contract_no: str
    start_date: date | None
    end_date: date | None
    sign_status: ContractSignStatus
    signed_at: datetime | None
    file_name: str | None
    mime_type: str | None
    file_size: int
    notes: str | None
    template_id: UUID | None = None
    created_at: datetime


class ContractTemplateFieldDef(BaseModel):
    """Satu baris `field_schema` template kontrak karyawan -- Fase 25.

    `type="list"` (+ `list_style`) BARU dari sini, belum ada di
    `presales.TemplateFieldDef` -- klausul kontrak bernomor/alfabet
    (mis. job description), item bisa tambah/hapus di UI."""

    key: str
    label: str
    type: str = "text"  # text | textarea | number | date | list
    list_style: str = "numeric"  # numeric | alpha -- dipakai kalau type == "list"


class EmploymentContractTemplateCreate(BaseModel):
    name: str
    field_schema: list[ContractTemplateFieldDef]
    footer_text: str | None = None


class EmploymentContractTemplateUpdate(BaseModel):
    name: str | None = None
    field_schema: list[ContractTemplateFieldDef] | None = None
    footer_text: str | None = None
    is_active: bool | None = None


class EmploymentContractTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    field_schema: list[ContractTemplateFieldDef]
    footer_text: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("field_schema", mode="before")
    @classmethod
    def _parse_field_schema(cls, v: object) -> object:
        return json.loads(v) if isinstance(v, str) else v


class ContractGenerateDocumentIn(BaseModel):
    template_id: UUID
    field_values: dict = {}


class ContractExpiringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_id: UUID
    contract_no: str
    employee_id: UUID
    employee_name: str
    employee_no: str
    end_date: date
    days_left: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    document_type: HrDocumentType
    title: str
    version: int
    file_name: str
    mime_type: str
    file_size: int
    notes: str | None
    uploaded_at: datetime


class WarningLetterCreate(BaseModel):
    letter_type: WarningLetterType
    reason: str
    issued_at: date | None = None


class WarningLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    letter_type: WarningLetterType
    reason: str
    issued_at: date
    valid_until: date | None
    is_active: bool
    file_name: str | None
    mime_type: str | None
    file_size: int
    issued_by: UUID | None
    created_at: datetime


class EmployeeMovementCreate(BaseModel):
    movement_type: MovementType
    previous_grade: str | None = None
    new_grade: str | None = None
    previous_level: str | None = None
    new_level: str | None = None
    previous_division: str | None = None
    new_division: str | None = None
    previous_position: str | None = None
    new_position: str | None = None
    effective_date: date
    notes: str | None = None


class EmployeeMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    movement_type: MovementType
    previous_grade: str | None
    new_grade: str | None
    previous_level: str | None
    new_level: str | None
    previous_division: str | None
    new_division: str | None
    previous_position: str | None
    new_position: str | None
    effective_date: date
    notes: str | None
    created_by: UUID | None
    created_at: datetime


class VaccineRecordCreate(BaseModel):
    vaccine_name: str
    dose_number: int = 1
    vaccinated_at: date
    location: str | None = None


class VaccineRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    vaccine_name: str
    dose_number: int
    vaccinated_at: date
    location: str | None
    created_at: datetime
