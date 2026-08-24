from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tenancy import TenantMixin


class AuditLog(TenantMixin, Base):
    """Jejak audit: siapa melakukan apa pada entitas/dokumen, kapan, dari mana.

    Sesuai PRD (keamanan): semua akses dokumen harus ter-audit. Baris log
    bersifat append-only — tidak ada endpoint ubah/hapus.
    tenant_id nullable: event pra-autentikasi (mis. login gagal) tidak
    selalu bisa dipetakan ke tenant.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Override kolom TenantMixin: boleh NULL untuk event sistem/pra-login.
    tenant_id: Mapped[UUID | None] = mapped_column(  # type: ignore[assignment]
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
