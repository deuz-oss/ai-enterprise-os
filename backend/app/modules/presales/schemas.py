import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.presales.models import ActivityType, AgreementStatus, LeadStage, QuotationStatus


class TemplateFieldDef(BaseModel):
    """Satu baris `field_schema` template dokumen (Quotation/Agreement/JO)."""

    key: str
    label: str
    type: str = "text"  # text | textarea | number | date


class QuotationTemplateCreate(BaseModel):
    name: str
    field_schema: list[TemplateFieldDef]
    footer_text: str | None = None
    accent_color: str = "#0f172a"


class QuotationTemplateUpdate(BaseModel):
    name: str | None = None
    field_schema: list[TemplateFieldDef] | None = None
    footer_text: str | None = None
    accent_color: str | None = None
    is_active: bool | None = None


class QuotationTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    field_schema: list[TemplateFieldDef]
    footer_text: str | None
    accent_color: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("field_schema", mode="before")
    @classmethod
    def _parse_field_schema(cls, v: object) -> object:
        # Kolom ORM-nya Text (JSON string) -- parse balik jadi list di sini
        # supaya response API tetap objek terstruktur, bukan string mentah.
        return json.loads(v) if isinstance(v, str) else v


class ContactCreate(BaseModel):
    name: str
    department: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    is_primary: bool | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    department: str | None
    email: str | None
    phone: str | None
    linkedin_url: str | None
    is_primary: bool
    created_at: datetime


class CompanyCreate(BaseModel):
    name: str
    industry: str | None = None
    size: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    size: str | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    industry: str | None
    size: str | None
    source: str
    created_at: datetime
    contacts: list[ContactOut] = []


class QuotationCreate(BaseModel):
    lead_id: UUID
    template_id: UUID
    field_values: dict[str, str | int | float]


class QuotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    template_id: UUID
    field_values: dict[str, str | int | float]
    status: QuotationStatus
    approved_by: UUID | None
    approved_at: datetime | None
    rejection_note: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("field_values", mode="before")
    @classmethod
    def _parse_field_values(cls, v: object) -> object:
        return json.loads(v) if isinstance(v, str) else v


class QuotationRejectIn(BaseModel):
    note: str


class AgreementTemplateCreate(BaseModel):
    name: str
    field_schema: list[TemplateFieldDef]
    footer_text: str | None = None


class AgreementTemplateUpdate(BaseModel):
    name: str | None = None
    field_schema: list[TemplateFieldDef] | None = None
    footer_text: str | None = None
    is_active: bool | None = None


class AgreementTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    field_schema: list[TemplateFieldDef]
    footer_text: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("field_schema", mode="before")
    @classmethod
    def _parse_field_schema(cls, v: object) -> object:
        return json.loads(v) if isinstance(v, str) else v


class AgreementCreate(BaseModel):
    lead_id: UUID
    template_id: UUID
    field_values: dict[str, str | int | float]


class AgreementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    template_id: UUID
    field_values: dict[str, str | int | float]
    status: AgreementStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    sent_at: datetime | None
    signed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("field_values", mode="before")
    @classmethod
    def _parse_field_values(cls, v: object) -> object:
        return json.loads(v) if isinstance(v, str) else v


class AgreementDeclineIn(BaseModel):
    note: str


class AgreementSendIn(BaseModel):
    signer_name: str
    signer_email: str


class LeadCreate(BaseModel):
    # Salah satu wajib: `company_id` (perusahaan sudah ada) ATAU
    # `company_name` (buat perusahaan baru inline -- kasus paling umum).
    # `contact_*` dipakai untuk membuat Contact utama pertama saat
    # perusahaan baru dibuat inline; diabaikan kalau `company_id` diisi
    # (tambah kontak lewat endpoint /companies/{id}/contacts terpisah).
    company_id: UUID | None = None
    company_name: str | None = None
    industry: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    estimated_headcount: int | None = None
    estimated_value: float | None = None
    stage: LeadStage = LeadStage.lead
    notes: str | None = None


class LeadUpdate(BaseModel):
    company_id: UUID | None = None
    estimated_headcount: int | None = None
    estimated_value: float | None = None
    stage: LeadStage | None = None
    notes: str | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    company_name: str
    industry: str | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: str | None
    estimated_headcount: int | None
    estimated_value: float | None
    stage: LeadStage
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ActivityCreate(BaseModel):
    activity_type: ActivityType = ActivityType.note
    content: str


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: ActivityType
    content: str
    created_at: datetime


class FunnelStage(BaseModel):
    stage: LeadStage
    count: int
    total_estimated_value: float


class FunnelStats(BaseModel):
    stages: list[FunnelStage]
    total_leads: int
    won_leads: int
    lost_leads: int
