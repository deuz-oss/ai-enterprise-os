from datetime import datetime
from uuid import UUID

from app.modules.ai_interview.models import (
    AIInterviewMode,
    AIInterviewResponseStatus,
    AIInterviewReviewStatus,
    AIInterviewTemplateStatus,
)
from app.modules.recruitment.models import PlacementStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_QUESTION_TYPES = ("open_ended", "single_choice", "multiple_choice", "rating")

# Fase 4 roadmap: pertanyaan yang menggali atribut yang dilindungi (UU
# Ketenagakerjaan Pasal 5-6: tanpa diskriminasi; UU PDP: data pribadi
# spesifik) ditolak saat template disimpan. Frasa sengaja spesifik ("agama
# anda", bukan "agama") supaya tidak salah tolak pertanyaan sah. Agen suara
# juga dilarang menanyakannya lewat aturan bawaan terkunci (service.py).
PROTECTED_QUESTION_TERMS = (
    "agama anda",
    "agamamu",
    "apa agama",
    "suku anda",
    "sukumu",
    "apa suku",
    "status pernikahan",
    "sudah menikah",
    "sudah berkeluarga",
    "sedang hamil",
    "rencana hamil",
    "rencana punya anak",
    "rencana memiliki anak",
    "orientasi seksual",
    "pilihan politik",
    "partai politik",
    "partai apa",
    "berapa usia anda",
    "berapa umur anda",
)


def _protected_hit(text: str) -> str | None:
    lowered = " ".join(text.lower().split())
    return next((t for t in PROTECTED_QUESTION_TERMS if t in lowered), None)


class InterviewQuestionBase(BaseModel):
    """Bentuk data pertanyaan tanpa validasi kebijakan -- dipakai untuk
    OUTPUT, supaya template lama yang tersimpan sebelum aturan baru tetap
    bisa dibaca (validasi hanya saat menyimpan, lewat InterviewQuestionIn)."""

    id: str
    order: int = 1
    type: str = "open_ended"
    prompt: str
    options: list[str] | None = None
    criterion_keys: list[str] = []
    required: bool = True
    # Fase 4 roadmap (mode suara real-time): berapa kali agen boleh bertanya
    # susulan untuk pertanyaan ini, dan apa yang digali. Batas dijaga kode
    # agen (bukan cuma prompt) supaya interview tidak melebar tanpa akhir.
    follow_up_max: int = Field(default=1, ge=0, le=3)
    follow_up_focus: str | None = Field(default=None, max_length=300)

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in _QUESTION_TYPES:
            raise ValueError(f"type harus salah satu dari: {', '.join(_QUESTION_TYPES)}")
        return v


class InterviewQuestionIn(InterviewQuestionBase):
    @model_validator(mode="after")
    def _no_protected_attribute(self) -> "InterviewQuestionIn":
        hit = _protected_hit(f"{self.prompt} {self.follow_up_focus or ''}")
        if hit:
            raise ValueError(
                f'Pertanyaan tidak boleh menanyakan "{hit}". Agama, suku, status '
                "pernikahan, kehamilan, usia, orientasi seksual, dan pandangan politik "
                "tidak boleh jadi bahan interview (UU Ketenagakerjaan Pasal 5-6)."
            )
        return self


class InterviewGuidelineBase(BaseModel):
    condition: str
    response: str


class InterviewGuidelineIn(InterviewGuidelineBase):
    """Pedoman percakapan agen suara, gaya Parlant: JIKA kondisi -> jawab.
    `response` diucapkan agen (hampir) persis -- jawaban baku yang sudah
    disetujui tim, bukan karangan LLM."""

    condition: str = Field(min_length=5, max_length=300)
    response: str = Field(min_length=5, max_length=600)

    @model_validator(mode="after")
    def _no_protected_probe(self) -> "InterviewGuidelineIn":
        hit = _protected_hit(self.response)
        if hit:
            raise ValueError(f'Jawaban pedoman tidak boleh menanyakan "{hit}".')
        return self


_MAX_GUIDELINES = 20


class InterviewGuidelineOut(BaseModel):
    """Pedoman yang dikirim ke agen. `locked` = aturan bawaan yang tidak bisa
    dikalahkan pedoman template; `source` = "sistem" | "template"."""

    key: str | None = None
    condition: str
    response: str
    locked: bool = False
    source: str = "template"


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


class InterviewCriterionBase(BaseModel):
    """Lihat InterviewQuestionBase -- untuk output, tanpa validasi kebijakan."""

    key: str
    label: str
    weight: float = 1.0
    description: str | None = None


class InterviewCriterionIn(InterviewCriterionBase):
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
    guidelines: list[InterviewGuidelineIn] = Field(default=[], max_length=_MAX_GUIDELINES)


class AIInterviewTemplateUpdate(BaseModel):
    title: str | None = None
    objective: str | None = None
    mode: AIInterviewMode | None = None
    status: AIInterviewTemplateStatus | None = None
    questions: list[InterviewQuestionIn] | None = None
    criteria: list[InterviewCriterionIn] | None = None
    guidelines: list[InterviewGuidelineIn] | None = Field(default=None, max_length=_MAX_GUIDELINES)


class AIInterviewTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_order_id: UUID | None
    title: str
    objective: str | None
    mode: AIInterviewMode
    status: AIInterviewTemplateStatus
    questions: list[InterviewQuestionBase]
    criteria: list[InterviewCriterionBase]
    guidelines: list[InterviewGuidelineBase] = []
    # Jumlah kandidat yang pernah diundang. > 0 = pertanyaan, kriteria & mode
    # terkunci (hasil lama harus tetap bisa dibandingkan) -> pakai duplikat.
    response_count: int = 0
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
    transcript_clean: str | None = None
    has_recording: bool = False
    recording_size_bytes: int | None = None
    ai_score_overall: int | None
    ai_score_original: int | None = None
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
    # Fase 5: tahap pipeline kandidat di job order template ini (Placement),
    # diisi service -- None bila template tanpa job order / belum di pipeline.
    placement_id: UUID | None = None
    placement_status: PlacementStatus | None = None


# Fase 5: tahap pipeline yang boleh dipilih reviewer dari halaman review AI
# Interview. Sengaja terbatas: lanjut ke klien atau gagal. Tahap sesudahnya
# (offering, OJT, onboarding) punya alur & dokumen sendiri di Recruitment.
REVIEW_PLACEMENT_STATUSES = (
    PlacementStatus.submitted,
    PlacementStatus.interview_client,
    PlacementStatus.rejected,
)


class AIInterviewReviewIn(BaseModel):
    review_status: AIInterviewReviewStatus
    review_notes: str | None = None
    ai_score_overall: int | None = None
    ai_score_breakdown: list[dict] | None = None
    # Keputusan pipeline SELALU eksplisit dari reviewer, terpisah dari
    # review_status (yang menilai hasil AI, bukan kandidat). Kosong = tidak
    # mengubah pipeline. AI tidak pernah memindahkan kandidat sendiri.
    placement_status: PlacementStatus | None = None
    placement_note: str | None = Field(default=None, max_length=1000)

    @field_validator("placement_status")
    @classmethod
    def _allowed_placement(cls, v: PlacementStatus | None) -> PlacementStatus | None:
        if v is not None and v not in REVIEW_PLACEMENT_STATUSES:
            allowed = ", ".join(s.value for s in REVIEW_PLACEMENT_STATUSES)
            raise ValueError(f"Tahap pipeline dari review AI Interview hanya: {allowed}")
        return v

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


class RecordedAnswerOut(BaseModel):
    """Status jawaban rekaman per pertanyaan (mode async_recording).
    Transkrip ditampilkan ke kandidat sendiri -- itu kata-katanya sendiri,
    dan membantu ia tahu apakah suaranya tertangkap dengan benar."""

    question_id: str
    status: str  # processing | ready | failed
    attempts_used: int
    transcript: str | None = None
    # Alasan gagal: "silent" (suara tidak tertangkap, memakai jatah) atau
    # "system" (gangguan server, jatah dikembalikan).
    failure: str | None = None


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
    # Fase 3: mode rekaman jawaban.
    recorded_answers: list[RecordedAnswerOut] = []
    max_attempts: int = 3
    max_answer_seconds: int = 180


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
    follow_up_max: int = 1
    follow_up_focus: str | None = None


class VoiceContextOut(BaseModel):
    """Konteks penuh untuk agent membangun system prompt percakapan --
    dipanggil agent lewat `GET .../voice/context`, kredensial `invite_token`
    yang sama, bukan endpoint kandidat."""

    title: str
    objective: str | None
    questions: list[VoiceContextQuestionOut]
    criteria: list[InterviewCriterionBase]
    # Fase 4: aturan bawaan (terkunci & default) lalu pedoman template.
    guidelines: list[InterviewGuidelineOut] = []


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


class CalibrationOut(BaseModel):
    """Fase 5: seberapa sering reviewer menyetujui/mengoreksi skor AI untuk
    satu template -- sinyal apakah rubrik/model perlu diperbaiki."""

    scored: int
    reviewed: int
    approved: int
    adjusted: int
    rejected: int
    # rata-rata |skor AI asli - skor reviewer| pada respons yang disesuaikan
    mean_adjustment: float | None
    # respons dengan >=1 kriteria yang hasil antar-run penilaiannya tidak stabil
    unstable: int


class RetentionRunOut(BaseModel):
    purged: int


class RecordingUrlOut(BaseModel):
    url: str
    expires_in_seconds: int
    # Urutan kanal file ogg (lihat agent/main.py).
    channels: list[str] = ["Kandidat", "Pewawancara AI"]
