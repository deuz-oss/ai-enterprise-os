"""Black Lists (riset arsitektur MyOHRIS §2, lihat plan file sesi ini) —
kapabilitas baru di bawah Talent Cloud, terhubung ke `Candidate` yang sudah
ada.

Pola request->approve, BUKAN langsung tandai kandidat "blacklisted" begitu
diajukan — sama seperti `AIInterviewResponse.review_status`/
`CONFIDENCE_THRESHOLD` di CV Intake: penanda reputasi (di sini: blacklist)
tidak pernah otomatis final dari satu aksi staf, wajib ada persetujuan
eksplisit terpisah dari yang mengajukan.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from app.core.database import Base
from app.core.tenancy import TenantMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class BlacklistStatus(str, enum.Enum):
    pending = "menunggu_review"
    approved = "disetujui"
    rejected = "ditolak"


class BlacklistEntry(TenantMixin, Base):
    __tablename__ = "blacklist_entries"
    __table_args__ = (
        Index("ix_blacklist_entries_tenant_status", "tenant_id", "status"),
        Index("ix_blacklist_entries_tenant_candidate", "tenant_id", "candidate_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[BlacklistStatus] = mapped_column(
        Enum(BlacklistStatus, native_enum=False, length=20),
        default=BlacklistStatus.pending,
        index=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
