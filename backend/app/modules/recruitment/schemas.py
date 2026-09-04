from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.recruitment.models import (
    CandidateStatus,
    InterviewType,
    JobOrderBusinessStatus,
    JobOrderStatus,
    PlacementStatus,
    ReferralRewardStatus,
)


class JobOrderTemplateCreate(BaseModel):
    name: str
    footer_text: str | None = None
    accent_color: str = "#0f172a"


class JobOrderTemplateUpdate(BaseModel):
    name: str | None = None
    footer_text: str | None = None
    accent_color: str | None = None
    is_active: bool | None = None


class JobOrderTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    footer_text: str | None
    accent_color: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobOrderGenerateDocumentIn(BaseModel):
    template_id: UUID


class ScreeningQuestion(BaseModel):
    id: str
    prompt: str
    required: bool = True


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
    is_public: bool = False
    public_client_label: str | None = None
    screening_questions: list[ScreeningQuestion] = []
    benefits: list[str] = []
    working_days: list[str] = []
    working_hours_start: time | None = None
    working_hours_end: time | None = None
    remote: bool = False
    office_address: str | None = None
    experience_level: str | None = None
    contract_detail: str | None = None
    industry: str | None = None
    position: str | None = None
    level: str | None = None
    package_detail: str | None = None


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
    is_public: bool | None = None
    public_client_label: str | None = None
    screening_questions: list[ScreeningQuestion] | None = None
    benefits: list[str] | None = None
    working_days: list[str] | None = None
    working_hours_start: time | None = None
    working_hours_end: time | None = None
    remote: bool | None = None
    office_address: str | None = None
    experience_level: str | None = None
    contract_detail: str | None = None
    industry: str | None = None
    position: str | None = None
    level: str | None = None
    package_detail: str | None = None


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
    is_public: bool
    public_client_label: str | None
    screening_questions: list[ScreeningQuestion]
    benefits: list[str]
    working_days: list[str]
    working_hours_start: time | None
    working_hours_end: time | None
    has_generated_document: bool
    generated_document_at: datetime | None
    remote: bool
    office_address: str | None
    experience_level: str | None
    contract_detail: str | None
    industry: str | None
    position: str | None
    level: str | None
    package_detail: str | None
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
    skills_list: list[str] = []
    source: str | None = None
    notes: str | None = None
    gender: str | None = None
    current_position: str | None = None
    birthdate: date | None = None
    birthplace: str | None = None
    address: str | None = None
    ktp_no: str | None = None
    marital_status: str | None = None
    blood_type: str | None = None
    religion: str | None = None
    languages: list[str] = []
    description: str | None = None
    position_pool: str | None = None
    job_level: str | None = None
    school: str | None = None
    education_level: str | None = None
    # Fase 27 -- kode referral karyawan yang mereferensikan kandidat ini
    # (input saja, resolusi ke `referred_by_employee_id` di service.py).
    referral_code: str | None = None


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
    skills_list: list[str] | None = None
    source: str | None = None
    status: CandidateStatus | None = None
    notes: str | None = None
    gender: str | None = None
    current_position: str | None = None
    birthdate: date | None = None
    birthplace: str | None = None
    address: str | None = None
    ktp_no: str | None = None
    marital_status: str | None = None
    blood_type: str | None = None
    religion: str | None = None
    languages: list[str] | None = None
    description: str | None = None
    position_pool: str | None = None
    job_level: str | None = None
    school: str | None = None
    education_level: str | None = None


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
    skills_list: list[str]
    source: str | None
    cv_file_name: str | None
    status: CandidateStatus
    notes: str | None
    reference: str | None
    gender: str | None
    current_position: str | None
    birthdate: date | None
    birthplace: str | None
    address: str | None
    ktp_no: str | None
    marital_status: str | None
    blood_type: str | None
    religion: str | None
    languages: list[str]
    description: str | None
    position_pool: str | None
    job_level: str | None
    school: str | None
    education_level: str | None
    referred_by_employee_id: UUID | None = None
    created_at: datetime


class CandidateExperienceCreate(BaseModel):
    company: str
    position: str
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class CandidateExperienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    company: str
    position: str
    start_date: date | None
    end_date: date | None
    description: str | None
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
    offering_call_done: bool
    offering_call_at: datetime | None
    created_at: datetime


class ReferralProgramSettingIn(BaseModel):
    is_enabled: bool
    reward_amount: float = 0


class ReferralProgramSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_enabled: bool
    reward_amount: float
    updated_at: datetime


class ReferralRewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    candidate_id: UUID
    placement_id: UUID | None
    amount: float
    eligible_at: date | None
    status: ReferralRewardStatus
    is_eligible: bool
    paid_at: datetime | None
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
