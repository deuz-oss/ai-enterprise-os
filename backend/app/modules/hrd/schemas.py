from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.hrd.models import (
    ContractSignStatus,
    EmployeeStatus,
    EmploymentType,
    HrDocumentType,
    MaritalStatus,
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
    created_at: datetime
    updated_at: datetime


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
    created_at: datetime


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
