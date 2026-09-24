from datetime import datetime
from uuid import UUID

from app.modules.ai_interview.models import (
    AIInterviewMode,
    AIInterviewResponseStatus,
    AIInterviewReviewStatus,
    AIInterviewTemplateStatus,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_QUESTION_TYPES = ("open_ended", "single_choice", "multiple_choice", "rating")


class InterviewQuestionIn(BaseModel):
    id: str
    order: int = 1
    type: str = "open_ended"
    prompt: str
    options: list[str] | None = None
    criterion_keys: list[str] = []
    required: bool = True

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in _QUESTION_TYPES:
            raise ValueError(f"type harus salah satu dari: {', '.join(_QUESTION_TYPES)}")
        return v


# Batas keras Fase 0 roadmap: AI Interview TIDAK menilai emosi, nada suara,
# ekspresi, atau cara bicara kandidat -- hanya ISI jawaban. EU AI Act
# melarang pengenalan emosi di konteks kerja/rekrutmen sejak Feb 2025, dan
# metrik "kefasihan"/aksen mendiskriminasi penutur daerah & penyandang
# gangguan bicara. Kriteria yang menyebut sinyal-sinyal ini ditolak saat
# template disimpan (lihat juga _SCORE_SYSTEM_PROMPT di service.py).
FORBIDDEN_CRITERIA_TERMS = (
    "emosi",
    "emotion",
    "nada suara",
    "intonasi",
    "tone of voice",
    "aksen",
    "accent",
    "logat",
    "ekspresi wajah",
    "facial",
    "mimik",
    "bahasa tubuh",
    "body language",
    "kefasihan bicara",
    "kelancaran bicara",
    "sentimen suara",
    "voice sentiment",
)


class InterviewCriterionIn(BaseModel):
    key: str
    label: str
    weight: float = 1.0
    description: str | None = None

    # model_validator (bukan field_validator "description"): validator field
    # tidak berjalan saat field memakai default, jadi kriteria TANPA
    # deskripsi akan lolos pengecekan key/label.
    @model_validator(mode="after")
    def _no_emotion_or_voice_signal(self) -> "InterviewCriterionIn":
        text = " ".join([self.key, self.label, self.description or ""]).lower()
        hit = next((t for t in FORBIDDEN_CRITERIA_TERMS if t in text), None)
        if hit:
            raise ValueError(
                f'Kriteria tidak boleh menilai "{hit}". AI Interview hanya menilai isi '
                "jawaban, bukan emosi, nada suara, ekspresi, atau cara bicara kandidat."
            )
        return self


class AIInterviewTemplateCreate(BaseModel):
    job_order_id: UUID | None = None
    title: str
    objective: str | None = None
    mode: AIInterviewMode = AIInterviewMode.async_text
    questions: list[InterviewQuestionIn] = []
    criteria: list[InterviewCriterionIn] = []


class AIInterviewTemplateUpdate(BaseModel):
    title: str | None = None
    objective: str | None = None
    mode: AIInterviewMode | None = None
    status: AIInterviewTemplateStatus | None = None
    questions: list[InterviewQuestionIn] | None = None
    criteria: list[InterviewCriterionIn] | None = None


class AIInterviewTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_order_id: UUID | None
    title: str
    objective: str | None
    mode: AIInterviewMode
    status: AIInterviewTemplateStatus
    questions: list[InterviewQuestionIn]
    criteria: list[InterviewCriterionIn]
    created_at: datetime
    updated_at: datetime


class AIInterviewInviteIn(BaseModel):
    candidate_ids: list[UUID]
    expires_in_hours: int = 72


class AIInterviewInviteResultItem(BaseModel):
    candidate_id: UUID
    response_id: UUID
    invite_token: str
    email_sent: bool


class AIInterviewInviteOut(BaseModel):
    invited: list[AIInterviewInviteResultItem]
    skipped: list[dict]


class AIInterviewResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    candidate_id: UUID
    job_order_id: UUID | None
    status: AIInterviewResponseStatus
    answers: list[dict]
    transcript_text: str | None
    ai_score_overall: int | None
    ai_score_breakdown: list[dict]
    ai_narrative: str | None
    ai_model: str | None
    review_status: AIInterviewReviewStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    invited_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None
    expires_at: datetime | None
    consent_given_at: datetime | None = None
    consent_version: str | None = None
    consent_withdrawn_at: datetime | None = None
    data_purged_at: datetime | None = None
    purge_reason: str | None = None


class AIInterviewReviewIn(BaseModel):
    review_status: AIInterviewReviewStatus
    review_notes: str | None = None
    ai_score_overall: int | None = None
    ai_score_breakdown: list[dict] | None = None

    @field_validator("review_status")
    @classmethod
    def _no_pending(cls, v: AIInterviewReviewStatus) -> AIInterviewReviewStatus:
        if v == AIInterviewReviewStatus.pending:
            raise ValueError("review_status tidak boleh diset balik ke pending")
        return v


# ---------- Sisi kandidat (publik, field terbatas — TANPA criterion_keys/weight) ----------


class PublicInterviewQuestionOut(BaseModel):
    id: str
    order: int
    type: str
    prompt: str
    options: list[str] | None


class PublicInterviewSessionOut(BaseModel):
    title: str
    objective: str | None
    status: AIInterviewResponseStatus
    mode: AIInterviewMode
    questions: list[PublicInterviewQuestionOut]
    expires_at: datetime | None
    # Fase 0: persetujuan wajib sebelum interview dimulai.
    consent_given: bool = False
    consent_version: str = ""
    consent_text: str = ""
    retention_days: int = 180
    data_withdrawn: bool = False


class AnswerIn(BaseModel):
    question_id: str
    answer_text: str


# ---------- AI Interview Fase 2: percakapan suara real-time ----------


class VoiceSessionOut(BaseModel):
    """Kredensial koneksi LiveKit untuk browser kandidat (`livekit-client`)."""

    url: str
    token: str


class VoiceContextQuestionOut(BaseModel):
    """Dipakai agent (BUKAN kandidat) -- boleh sertakan `criterion_keys`,
    beda dari `PublicInterviewQuestionOut` yang sengaja menyembunyikannya."""

    id: str
    order: int
    prompt: str
    criterion_keys: list[str]


class VoiceContextOut(BaseModel):
    """Konteks penuh untuk agent membangun system prompt percakapan --
    dipanggil agent lewat `GET .../voice/context`, kredensial `invite_token`
    yang sama, bukan endpoint kandidat."""

    title: str
    objective: str | None
    questions: list[VoiceContextQuestionOut]
    criteria: list[InterviewCriterionIn]


class VoiceCompleteIn(BaseModel):
    transcript: str


# ---------- Fase 0: persetujuan & retensi ----------


class AIInterviewSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retention_days: int


class AIInterviewSettingsUpdate(BaseModel):
    # 30 hari minimum supaya proses review sempat selesai; 2 tahun maksimum
    # supaya "disimpan sepanjang diperlukan" (UU PDP) tidak jadi selamanya.
    retention_days: int = Field(ge=30, le=730)


class RetentionRunOut(BaseModel):
    purged: int
