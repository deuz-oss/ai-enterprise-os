"""AI Interview (PRD v3.1 Patch 4) — kapabilitas baru di bawah Talent Cloud.

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

    ai_score_overall: Mapped[int | None] = mapped_column(Integer)
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
    def ai_score_breakdown(self) -> list[dict]:
        try:
            data = json.loads(self.ai_score_breakdown_json) if self.ai_score_breakdown_json else []
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []
