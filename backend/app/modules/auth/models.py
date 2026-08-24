import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    business_dev = "business_dev"
    recruiter = "recruiter"
    hr = "hr"
    operations = "operations"
    finance = "finance"
    management = "management"
    # Pengelola platform SaaS: tanpa tenant, hanya boleh ke /platform/*
    platform_admin = "platform_admin"
    # Karyawan outsourcing: self-service (portal saya) — dibuat oleh HR
    employee = "karyawan"


class PasswordResetToken(Base):
    """Token reset password satu kali pakai (disimpan sebagai hash SHA-256)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # NULL = akun level platform (platform_admin), bukan milik tenant manapun.
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=50), default=UserRole.management
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
