import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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


class CandidateStatus(str, enum.Enum):
    new = "baru"
    screening = "screening"
    interview = "interview"
    offered = "offered"
    placed = "placed"
    rejected = "gagal"
    archived = "arsip"


class PlacementStatus(str, enum.Enum):
    proposed = "diusulkan"
    accepted = "disetujui_klien"
    onboarded = "onboarded"
    cancelled = "dibatalkan"


class InterviewStatus(str, enum.Enum):
    scheduled = "terjadwal"
    done = "selesai"
    no_show = "tidak_hadir"
    cancelled = "dibatalkan"


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", lazy="joined")
    placements: Mapped[list["Placement"]] = relationship(back_populates="job_order")


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
        Enum(PlacementStatus, native_enum=False, length=50), default=PlacementStatus.proposed
    )
    # PRD v3.0 §4 aksi "Offering": surat penawaran PDF dibrandingi + esign.
    offering_letter_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    offering_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", lazy="joined")
    job_order = relationship("JobOrder", back_populates="placements", lazy="joined")
