"""AI Interview (PRD v3.1 Patch 4) — kapabilitas baru di bawah Recruitment.

Definisi interview (`AIInterviewTemplate`: pertanyaan+kriteria) terpisah dari
instance/jawaban (`AIInterviewResponse`) — pola dari riset arsitektur (FoloUp/
Aural), TERPISAH dari `InterviewSchedule` yang sudah ada (itu untuk interview
manusia terjadwal — kardinalitas beda: satu jadwal = satu event, AI interview
bisa diulang/dinilai ulang, dan `InterviewSchedule` tidak punya kolom
transkrip/skor-breakdown/review).

MVP mode `async_text` saja (kandidat ketik jawaban, dinilai belakangan) —
`async_recording`/`realtime_voice` disiapkan sebagai nilai enum untuk fase
berikutnya, belum ada endpoint upload/transcribe di pass ini.

Skor AI TIDAK PERNAH otomatis jadi keputusan final — `review_status` default
`pending`, wajib aksi eksplisit reviewer (pola sama seperti
`CONFIDENCE_THRESHOLD` di CV Intake).
"""

from __future__ import annotations

import enum
import json
from datetime import datetime
from uuid import UUID, uuid4

from app.core.database import Base
from app.core.tenancy import TenantMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class AIInterviewMode(str, enum.Enum):
    async_text = "async_text"
    async_recording = "async_recording"
    realtime_voice = "realtime_voice"


class AIInterviewTemplateStatus(str, enum.Enum):
    draft = "draft"
    active = "aktif"
    archived = "arsip"


class AIInterviewTemplate(TenantMixin, Base):
    __tablename__ = "ai_interview_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_orders.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[AIInterviewMode] = mapped_column(
        Enum(AIInterviewMode, native_enum=False, length=20), default=AIInterviewMode.async_text
    )
    status: Mapped[AIInterviewTemplateStatus] = mapped_column(
        Enum(AIInterviewTemplateStatus, native_enum=False, length=20),
        default=AIInterviewTemplateStatus.draft,
        index=True,
    )
    questions_json: Mapped[str] = mapped_column(Text, default="[]")
    criteria_json: Mapped[str] = mapped_column(Text, default="[]")
    # Fase 4 roadmap: pedoman percakapan agen suara (lihat
    # service.BUILTIN_GUIDELINES untuk aturan bawaan yang selalu berlaku).
    guidelines_json: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def questions(self) -> list[dict]:
        try:
            data = json.loads(self.questions_json) if self.questions_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []

    @property
    def criteria(self) -> list[dict]:
        try:
            data = json.loads(self.criteria_json) if self.criteria_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []

    @property
    def guidelines(self) -> list[dict]:
        try:
            data = json.loads(self.guidelines_json) if self.guidelines_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []


class AIInterviewResponseStatus(str, enum.Enum):
    invited = "diundang"
    in_progress = "berlangsung"
    submitted = "terkirim"
    scored = "dinilai"
    expired = "kedaluwarsa"


class AIInterviewReviewStatus(str, enum.Enum):
    pending = "menunggu_review"
    approved = "disetujui"
    adjusted = "disesuaikan"
    rejected = "ditolak"


class AIInterviewResponse(TenantMixin, Base):
    __tablename__ = "ai_interview_responses"
    __table_args__ = (
        Index("ix_ai_interview_resp_tenant_status", "tenant_id", "status"),
        Index("ix_ai_interview_resp_tenant_review", "tenant_id", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("ai_interview_templates.id"), index=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_orders.id"), nullable=True, index=True
    )

    invite_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[AIInterviewResponseStatus] = mapped_column(
        Enum(AIInterviewResponseStatus, native_enum=False, length=20),
        default=AIInterviewResponseStatus.invited,
        index=True,
    )

    answers_json: Mapped[str | None] = mapped_column(Text)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    # Fase 2 roadmap: transkrip mentah (`transcript_text`) tetap SATU-SATUNYA
    # dasar penilaian & kutipan bukti; versi dirapikan (tanpa "eh/anu",
    # pengulangan) hanya untuk dibaca reviewer.
    transcript_clean: Mapped[str | None] = mapped_column(Text)
    # Rekaman sesi suara (ogg/opus 2 kanal: 0 = kandidat, 1 = pewawancara AI),
    # direkam di agent lalu disimpan di object storage. Dihapus bersama isi
    # lain saat retensi/penarikan persetujuan (`_purge_content`).
    recording_object_key: Mapped[str | None] = mapped_column(String(500))
    recording_size_bytes: Mapped[int | None] = mapped_column(Integer)

    ai_score_overall: Mapped[int | None] = mapped_column(Integer)
    # Fase 5 roadmap: skor AI sebelum disesuaikan reviewer (NULL = tidak
    # pernah disesuaikan) -- bahan kalibrasi AI vs penilaian manusia.
    ai_score_original: Mapped[int | None] = mapped_column(Integer)
    ai_score_breakdown_json: Mapped[str | None] = mapped_column(Text)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(120))

    review_status: Mapped[AIInterviewReviewStatus] = mapped_column(
        Enum(AIInterviewReviewStatus, native_enum=False, length=20),
        default=AIInterviewReviewStatus.pending,
        index=True,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Fase 0 roadmap (UU PDP No. 27/2022): persetujuan eksplisit kandidat
    # sebelum jawaban/suaranya diproses AI. `consent_version` menunjuk teks
    # persetujuan yang disetujui (lihat service.CONSENT_VERSION) -- kalau
    # teksnya berubah, bukti persetujuan lama tetap bisa ditelusuri.
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(String(20))
    consent_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Isi (jawaban, transkrip, hasil AI, catatan review) dikosongkan saat
    # masa retensi habis atau persetujuan ditarik; baris & status tetap ada
    # sebagai jejak proses rekrutmen tanpa data pribadinya.
    data_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_reason: Mapped[str | None] = mapped_column(String(30))

    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def answers(self) -> list[dict]:
        try:
            data = json.loads(self.answers_json) if self.answers_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []

    @property
    def has_recording(self) -> bool:
        return self.recording_object_key is not None

    @property
    def ai_score_breakdown(self) -> list[dict]:
        try:
            data = json.loads(self.ai_score_breakdown_json) if self.ai_score_breakdown_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []


class AIInterviewSettings(TenantMixin, Base):
    """Pengaturan AI Interview per tenant (satu baris, dibuat on-demand --
    pola sama `HrDocumentSettings`). `retention_days`: berapa lama jawaban,
    transkrip, dan hasil AI disimpan setelah interview dikirim sebelum
    dihapus otomatis (UU PDP: data disimpan sepanjang diperlukan saja)."""

    __tablename__ = "ai_interview_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    retention_days: Mapped[int] = mapped_column(Integer, default=180)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
