from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.recruitment.models import (
    CandidateStatus,
    InterviewType,
    JobOrderBusinessStatus,
    JobOrderStatus,
    PlacementStatus,
)


class JobOrderCreate(BaseModel):
    client_id: UUID
    title: str
    headcount: int = 1
    description: str | None = None
    requirements: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    due_date: date | None = None
    request_id: str | None = None  # kosong -> auto-generate JO/{tahun}/{urutan}
    request_date: date | None = None  # kosong -> default hari ini
    area: str | None = None
    contract_duration_months: int | None = None
    gross_salary: float | None = None
    business_status: JobOrderBusinessStatus = JobOrderBusinessStatus.open
    requires_ojt: bool = False
    source_document_object_key: str | None = None
    source_document_file_name: str | None = None


class JobOrderUpdate(BaseModel):
    title: str | None = None
    headcount: int | None = None
    description: str | None = None
    requirements: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    due_date: date | None = None
    status: JobOrderStatus | None = None
    request_id: str | None = None
    request_date: date | None = None
    area: str | None = None
    contract_duration_months: int | None = None
    gross_salary: float | None = None
    business_status: JobOrderBusinessStatus | None = None
    requires_ojt: bool | None = None


class JobOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    title: str
    headcount: int
    description: str | None
    requirements: str | None
    salary_min: float | None
    salary_max: float | None
    due_date: date | None
    status: JobOrderStatus
    request_id: str | None
    request_date: date
    area: str | None
    contract_duration_months: int | None
    gross_salary: float | None
    business_status: JobOrderBusinessStatus
    requires_ojt: bool
    is_stale: bool
    source_document_file_name: str | None
    has_source_document: bool
    created_at: datetime


class JobOrderExtractOut(BaseModel):
    """Hasil ekstraksi AI dari dokumen Job Order — saran field, belum jadi JobOrder."""

    object_key: str
    file_name: str
    requisition_code: str | None = None
    job_title: str | None = None
    client_name: str | None = None
    area_location: str | None = None
    headcount: int | None = None
    request_effective_date: date | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_duration_months: int | None = None
    gross_basic_salary: float | None = None
    mandatory_criteria: list[str] = []
    preferred_criteria: list[str] = []
    job_description_summary: str | None = None


class CandidateCreate(BaseModel):
    full_name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    education: str | None = None
    experience_years: int | None = 0
    current_company: str | None = None
    expected_salary: float | None = None
    skills: str | None = None
    source: str | None = None
    notes: str | None = None


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    education: str | None = None
    experience_years: int | None = None
    current_company: str | None = None
    expected_salary: float | None = None
    skills: str | None = None
    source: str | None = None
    status: CandidateStatus | None = None
    notes: str | None = None


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    phone: str | None
    email: str | None
    city: str | None
    education: str | None
    experience_years: int | None
    current_company: str | None
    expected_salary: float | None
    skills: str | None
    source: str | None
    cv_file_name: str | None
    status: CandidateStatus
    notes: str | None
    created_at: datetime


class PlacementCreate(BaseModel):
    candidate_id: UUID
    job_order_id: UUID
    offered_salary: float | None = None
    start_date: date | None = None


class PlacementUpdate(BaseModel):
    status: PlacementStatus
    offered_salary: float | None = None
    start_date: date | None = None
    ojt_start_date: date | None = None
    ojt_end_date: date | None = None


class PlacementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    job_order_id: UUID
    offered_salary: float | None
    start_date: date | None
    status: PlacementStatus
    ojt_start_date: date | None
    ojt_end_date: date | None
    created_at: datetime


class OfferingSendIn(BaseModel):
    """PRD v3.0 §4 aksi "Offering": kirim surat penawaran ke kandidat via TTE."""

    signer_name: str
    signer_email: str
    offered_salary: float | None = None
    start_date: date | None = None


class OfferingSummaryItem(BaseModel):
    placement_id: UUID
    candidate_name: str
    job_order_title: str
    client_name: str
    offered_salary: float | None
    esign_status: str | None
    """None = surat sudah dibuat tapi belum sempat dikirim ke TTE."""


class OfferingSummaryOut(BaseModel):
    total_active: int
    awaiting_signature: int
    items: list[OfferingSummaryItem]


class InterviewScheduleCreate(BaseModel):
    candidate_id: UUID
    job_order_id: UUID
    interviewer_id: UUID | None = None
    scheduled_at: datetime
    location: str | None = None
    meeting_url: str | None = None
    interview_type: InterviewType = InterviewType.internal


class InterviewScheduleUpdate(BaseModel):
    scheduled_at: datetime | None = None
    location: str | None = None
    meeting_url: str | None = None
    status: str | None = None
    feedback: str | None = None
    score: int | None = None
    interview_type: InterviewType | None = None


class InterviewScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    job_order_id: UUID
    interviewer_id: UUID | None
    scheduled_at: datetime
    location: str | None
    meeting_url: str | None
    status: str
    interview_type: InterviewType
    feedback: str | None
    score: int | None
    created_at: datetime


class MatchRequest(BaseModel):
    top_k: int = 50


class MatchResult(BaseModel):
    candidate_id: UUID
    match_score: int
    explain: str
    missing: list[str] = []
