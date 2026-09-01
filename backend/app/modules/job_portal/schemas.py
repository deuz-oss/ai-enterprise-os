from datetime import datetime
from uuid import UUID

from app.modules.recruitment.schemas import ScreeningQuestion
from pydantic import BaseModel


class PublicJobOrderOut(BaseModel):
    """Field aman untuk listing lowongan publik — TIDAK PERNAH sertakan
    client.name asli, cuma public_client_label (atau label generik)."""

    id: UUID
    title: str
    client_label: str
    area: str | None
    gross_salary: float | None
    salary_min: float | None
    salary_max: float | None
    contract_duration_months: int | None
    headcount: int
    requirements: str | None
    question_count: int


class PublicJobOrderDetailOut(PublicJobOrderOut):
    description: str | None
    screening_questions: list[ScreeningQuestion]


class ApplyIn(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    consent: bool = False
    screening_answers: dict[str, str] = {}


class JobApplicationOut(BaseModel):
    application_token: str
    message: str


class ApplicationStatusOut(BaseModel):
    job_title: str
    candidate_name: str
    status_label: str
    submitted_at: datetime | None
