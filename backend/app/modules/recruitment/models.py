import enum
import json
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class JobOrderStatus(str, enum.Enum):
    open = "open"
    screening = "screening"
    interview = "interview_klien"
    offering = "offering"
    filled = "filled"
    closed = "closed"


class JobOrderBusinessStatus(str, enum.Enum):
    """Status bisnis JO level tinggi (PRD v3.1 Patch 3) — berbeda dari
    JobOrderStatus di atas yang melacak tahap pipeline rekrutmen internal."""

    open = "dibuka"
    on_hold = "ditahan"
    cancelled = "dibatalkan"
    filled = "terisi"


class CandidateStatus(str, enum.Enum):
    new = "baru"
    screening = "screening"
    interview = "interview"
    offered = "offered"
    placed = "placed"
    rejected = "gagal"
    archived = "arsip"


class PlacementStatus(str, enum.Enum):
    """Pipeline sourcing->onboarding per pasangan kandidat-JO (PRD v3.1 Patch 2).

    8 tahap baru ditambah SEBELUM `proposed` — makna proposed/accepted/
    onboarded/cancelled TIDAK berubah (tetap dipakai alur offering/esign
    yang sudah ada). `sourced` jadi status default baru saat Placement
    dibuat (sebelumnya `proposed`) — Placement sekarang dibuat sejak momen
    kandidat ditautkan ke JO (sourcing), bukan baru saat siap ditawari.
    """

    sourced = "disourcing"
    screening = "screening"
    interview_internal = "interview_rekruter"
    submitted = "disubmit"
    sent_to_client = "dikirim_ke_klien"
    client_screening = "screening_klien"
    interview_client = "interview_klien"
    ojt = "ojt"
    proposed = "diusulkan"
    accepted = "disetujui_klien"
    onboarded = "onboarded"
    rejected = "gagal"
    cancelled = "dibatalkan"


class InterviewStatus(str, enum.Enum):
    scheduled = "terjadwal"
    done = "selesai"
    no_show = "tidak_hadir"
    cancelled = "dibatalkan"


class InterviewType(str, enum.Enum):
    """Interview rekruter internal vs interview user oleh klien (PRD v3.1 Patch 2)."""

    internal = "internal"
    klien = "klien"


class InterviewSchedule(TenantMixin, Base):
    """Jadwal interview — PRD v3.0 Talent Cloud."""

    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID] = mapped_column(ForeignKey("job_orders.id"), index=True)
    interviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(255), default=None)
    meeting_url: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, native_enum=False, length=50),
        default=InterviewStatus.scheduled,
        index=True,
    )
    interview_type: Mapped[InterviewType] = mapped_column(
        Enum(InterviewType, native_enum=False, length=20),
        default=InterviewType.internal,
        index=True,
    )
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    score: Mapped[int | None] = mapped_column(Integer, default=None)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobOrder(TenantMixin, Base):
    __tablename__ = "job_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    headcount: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    salary_max: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[JobOrderStatus] = mapped_column(
        Enum(JobOrderStatus, native_enum=False, length=50),
        default=JobOrderStatus.open,
        index=True,
    )
    # PRD v3.1 Patch 3 — field operasional tambahan
    request_id: Mapped[str | None] = mapped_column(String(50), index=True)
    request_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    area: Mapped[str | None] = mapped_column(String(120))
    contract_duration_months: Mapped[int | None] = mapped_column(Integer)
    gross_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    business_status: Mapped[JobOrderBusinessStatus] = mapped_column(
        # values_callable wajib: nama anggota enum ini beda dari nilai
        # string-nya (open="dibuka", dst), dan create/update job order lewat
        # payload.model_dump() yang "membuka" enum jadi nilai mentah sebelum
        # disimpan -- tanpa ini SQLAlchemy simpan/cari berdasar NAMA anggota,
        # bentrok dengan nilai yang sebenarnya ada di kolom -> LookupError
        # saat baca baris manapun.
        Enum(
            JobOrderBusinessStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=JobOrderBusinessStatus.open,
        index=True,
    )
    # PRD v3.1 Patch 2 — kondisional per JO, bukan per Client
    requires_ojt: Mapped[bool] = mapped_column(Boolean, default=False)
    # PRD v3.1 Patch 3b — dokumen Job Order/Manpower Requisition sumber (opsional)
    source_document_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    source_document_file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    # PRD v3.1 Patch 5 — Job Portal: opt-in publik per JO
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nama klien tersamar utk lowongan publik — TIDAK PERNAH fallback ke
    # client.name asli (temuan dari dokumen JO sungguhan: klien bisa minta
    # identitasnya disembunyikan dari iklan lowongan publik).
    public_client_label: Mapped[str | None] = mapped_column(String(255), default=None)
    screening_questions_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", lazy="joined")
    placements: Mapped[list["Placement"]] = relationship(back_populates="job_order")

    @property
    def is_stale(self) -> bool:
        """Alert: JO masih dibuka DAN request_date >= 30 hari lalu (PRD v3.1 Patch 3)."""
        if self.business_status != JobOrderBusinessStatus.open:
            return False
        return (date.today() - self.request_date).days >= 30

    @property
    def has_source_document(self) -> bool:
        return self.source_document_object_key is not None

    @property
    def screening_questions(self) -> list[dict]:
        if not self.screening_questions_json:
            return []
        try:
            parsed = json.loads(self.screening_questions_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []


class Candidate(TenantMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    education: Mapped[str | None] = mapped_column(String(255))
    experience_years: Mapped[int | None] = mapped_column(Integer, default=0)
    current_company: Mapped[str | None] = mapped_column(String(255))
    expected_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    skills: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(120))
    cv_object_key: Mapped[str | None] = mapped_column(String(500))
    cv_file_name: Mapped[str | None] = mapped_column(String(255))
    # Foto kandidat untuk CV standar (ditampilkan bila branding tenant mengizinkan)
    photo_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, native_enum=False, length=50),
        default=CandidateStatus.new,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Placement(TenantMixin, Base):
    __tablename__ = "placements"
    __table_args__ = (UniqueConstraint("candidate_id", "job_order_id", name="uq_candidate_jo"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID] = mapped_column(ForeignKey("job_orders.id"), index=True)
    offered_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[PlacementStatus] = mapped_column(
        # PRD v3.1 Patch 2: default sekarang `sourced` (bukan `proposed`) —
        # Placement dibuat sejak momen sourcing, bukan cuma saat siap ditawari.
        Enum(PlacementStatus, native_enum=False, length=50),
        default=PlacementStatus.sourced,
    )
    # PRD v3.1 Patch 2 — OJT kondisional, dilewati kalau JobOrder.requires_ojt=False
    ojt_start_date: Mapped[date | None] = mapped_column(Date, default=None)
    ojt_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    # PRD v3.0 §4 aksi "Offering": surat penawaran PDF dibrandingi + esign.
    offering_letter_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    offering_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # PRD v3.1 Patch 5 — Job Portal: NULL kalau sourcing dari Talent Pool
    # internal, terisi kalau kandidat apply sendiri lewat portal publik.
    application_token: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    screening_answers: Mapped[str | None] = mapped_column(Text, default=None)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", lazy="joined")
    job_order = relationship("JobOrder", back_populates="placements", lazy="joined")
