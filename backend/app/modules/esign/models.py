import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tenancy import TenantMixin


class EsignStatus(str, enum.Enum):
    sent = "terkirim"
    viewed = "dilihat"
    completed = "selesai"
    declined = "ditolak"
    expired = "kedaluwarsa"
    failed = "gagal"


class EsignRequest(TenantMixin, Base):
    """Permintaan tanda tangan elektronik atas kontrak kerja ATAU surat
    penawaran kerja (PRD v3.0 §4 aksi "Offering") — tepat satu dari
    `contract_id`/`placement_id` terisi, sisanya NULL.
    """

    __tablename__ = "esign_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    contract_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employment_contracts.id"), nullable=True, index=True
    )
    placement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("placements.id"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    provider_document_id: Mapped[str] = mapped_column(String(255), index=True)
    signer_name: Mapped[str] = mapped_column(String(255))
    signer_email: Mapped[str] = mapped_column(String(255))
    sign_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EsignStatus] = mapped_column(
        Enum(EsignStatus, native_enum=False, length=50),
        default=EsignStatus.sent,
        index=True,
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    # Payload mentah dari webhook/status provider untuk kebutuhan audit.
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
