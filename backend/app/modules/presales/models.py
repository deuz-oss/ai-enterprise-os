import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LeadStage(str, enum.Enum):
    lead = "lead"
    contact = "kontak"
    presentation = "presentasi"
    quotation = "penawaran"
    negotiation = "negosiasi"
    won = "deal"
    lost = "gagal"


class ActivityType(str, enum.Enum):
    call = "telepon"
    meeting = "meeting"
    email = "email"
    note = "catatan"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(60))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    estimated_headcount: Mapped[int | None] = mapped_column(default=None)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(16, 2), default=None)
    stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, native_enum=False, length=50), default=LeadStage.lead, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadActivity.created_at"
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, native_enum=False, length=50), default=ActivityType.note
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="activities")
