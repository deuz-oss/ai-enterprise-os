import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClientStatus(str, enum.Enum):
    active = "aktif"
    churned = "berhenti"


class DocumentType(str, enum.Enum):
    pks = "perjanjian_kerjasama"
    addendum = "addendum"
    npwp = "npwp"
    nib = "nib"
    other = "lainnya"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    npwp: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    pic_name: Mapped[str | None] = mapped_column(String(255))
    pic_phone: Mapped[str | None] = mapped_column(String(60))
    pic_email: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, native_enum=False, length=50), default=ClientStatus.active
    )
    contract_start: Mapped[date | None] = mapped_column(Date, default=None)
    contract_end: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("leads.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["LegalDocument"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="LegalDocument.uploaded_at"
    )


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=50), default=DocumentType.other
    )
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    object_key: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped[Client] = relationship(back_populates="documents")
