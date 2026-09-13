from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tenancy import TenantMixin


class GoogleMailboxConnection(TenantMixin, Base):
    """Fase 47 -- koneksi akun Google (Gmail + Calendar) milik SATU staf
    (bukan tenant-wide), dipakai untuk sync email/meeting ke `LeadActivity`
    secara on-demand per lead (tombol "Sync Google" -- TIDAK ada scheduler
    background di codebase ini, dikonfirmasi saat riset billing cycle-close
    Fase 28: pola yang ada untuk kerja periodik adalah endpoint internal
    dipicu cron OS eksternal, tidak relevan untuk sync per-user per-klik
    seperti ini).

    Token disimpan APA ADANYA (bukan dienkripsi) -- konsisten dengan postur
    keamanan kredensial eksternal yang sudah ada di codebase ini (mis.
    PRIVY_USERNAME/PASSWORD di `core/config.py` juga plaintext env var),
    bukan standar baru yang diperkenalkan di sini."""

    __tablename__ = "google_mailbox_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_google_mailbox_user"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    google_email: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
