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


class JobOrder(Base):
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


class Candidate(Base):
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


class Placement(Base):
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", lazy="joined")
    job_order = relationship("JobOrder", back_populates="placements", lazy="joined")
