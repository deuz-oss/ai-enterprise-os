import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class ClientStatus(str, enum.Enum):
    active = "aktif"
    churned = "berhenti"


class DocumentType(str, enum.Enum):
    pks = "perjanjian_kerjasama"
    addendum = "addendum"
    npwp = "npwp"
    nib = "nib"
    other = "lainnya"


class Client(TenantMixin, Base):
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
    # PRD v3.0 auto prospek→aktif
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
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


class LegalDocument(TenantMixin, Base):
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


class ClientPortalAccess(TenantMixin, Base):
    """Akses portal monitoring read-only untuk klien (link tanpa akun).

    BEDA dari `payroll.PayrollRunToken`/`hrd.OnboardingInvite` yang
    sekali-pakai/kedaluwarsa pendek: token ini PERSISTEN -- klien kembali
    berkali-kali tiap bulan untuk cek kehadiran/lembur karyawannya, tidak
    ada konsep "sudah diputuskan". Dicabut/diganti HR secara eksplisit
    (`service.generate_portal_access`/`revoke_portal_access`), bukan
    expired otomatis."""

    __tablename__ = "client_portal_access"
    __table_args__ = (UniqueConstraint("client_id", name="uq_client_portal_access_client"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientSite(TenantMixin, Base):
    """Titik lokasi kantor/cabang klien untuk geofencing absensi (Fase 34).

    Radius ditempel di sini, bukan di `Client` -- klien multi-cabang bisa
    punya banyak site dengan radius beda-beda, dan job order baru di
    cabang yang sama tinggal reuse site yang sudah ada alih-alih isi
    ulang lokasi. `Employee.site_id` (nullable) menentukan mode: kosong =
    absen bebas (perilaku lama, tidak berubah), terisi = wajib dalam
    radius site ini saat clock-in/out (`ess/service.py::mobile_clock`)."""

    __tablename__ = "client_sites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    radius_meters: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
