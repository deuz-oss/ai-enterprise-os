import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tenancy import TenantMixin


class TenantStatus(str, enum.Enum):
    active = "aktif"
    suspended = "ditangguhkan"


class LicenseStatus(str, enum.Enum):
    trial = "trial"
    active = "aktif"
    expired = "kedaluwarsa"


class Tenant(Base):
    """Tenant = satu perusahaan outsourcing pelanggan SaaS."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=False, length=50), default=TenantStatus.active
    )
    # PRD v3.0 per-tenant billing override (inherit = ikut APP_MODE global)
    billing_mode: Mapped[str] = mapped_column(String(20), default="inherit")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantAppLicense(TenantMixin, Base):
    """Lisensi satu aplikasi portofolio untuk satu tenant (Fase 7).

    - trial: aktif selama 14 hari sejak started_at (aktivasi mandiri).
    - aktif: berlangganan; expires_at NULL = tanpa batas waktu.
    - kedaluwarsa: ditandai platform admin / hasil trial hangus.

    Guard endpoint membaca baris ini; tanpa baris = belum berlisensi.
    """

    __tablename__ = "tenant_app_licenses"
    __table_args__ = (UniqueConstraint("tenant_id", "app_key", name="uq_license_tenant_app"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    app_key: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, native_enum=False, length=50), default=LicenseStatus.trial
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
