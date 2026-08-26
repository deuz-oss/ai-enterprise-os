import enum
from datetime import datetime
from uuid import UUID, uuid4

from app.core.database import Base
from app.core.tenancy import TenantMixin
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class CvDocKind(str, enum.Enum):
    pdf_text = "pdf_text"
    pdf_scan = "pdf_scan"
    docx = "docx"
    image = "image"


class IntakeStatus(str, enum.Enum):
    uploaded = "terunggah"
    processing = "diproses"
    review = "menunggu_review"
    finalized = "finalisasi"
    failed = "gagal"


class TalentPoolStatus(str, enum.Enum):
    """Meta status talent pool (PRD §10.2)."""

    baru = "baru"
    diproses = "diproses"
    placed = "placed"
    non_aktif = "non_aktif"


class CvIntake(TenantMixin, Base):
    """Satu proses intake CV (Fase 13): unggah → ekstraksi → review → finalisasi.

    File asli tidak pernah ditimpa/dihapus — tersimpan di storage sebagai bukti
    sumber; pipeline dapat dijalankan ulang saat skema/prompt naik versi.
    """

    __tablename__ = "cv_intakes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    uploaded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    source: Mapped[str] = mapped_column(String(120), default="upload")
    doc_kind: Mapped[CvDocKind | None] = mapped_column(
        Enum(CvDocKind, native_enum=False, length=20), default=None
    )
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[IntakeStatus] = mapped_column(
        Enum(IntakeStatus, native_enum=False, length=50),
        default=IntakeStatus.uploaded,
        index=True,
    )
    # Hasil ekstraksi & meta kualitas (JSON serial)
    extracted: Mapped[str | None] = mapped_column()
    confidences: Mapped[str | None] = mapped_column()
    needs_review: Mapped[str | None] = mapped_column()
    reviewed_fields: Mapped[str | None] = mapped_column()

    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    prompt_version: Mapped[int] = mapped_column(Integer, default=1)
    readiness: Mapped[str | None] = mapped_column(String(30))
    tp_status: Mapped[TalentPoolStatus] = mapped_column(
        Enum(TalentPoolStatus, native_enum=False, length=50),
        default=TalentPoolStatus.baru,
        index=True,
    )
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(500))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StandardCvVersion(TenantMixin, Base):
    """Snapshot PDF CV standar per kandidat; tiap finalisasi membuat versi baru.

    Saat kandidat disubmit ke job order, versi terkunci ikut tersimpan sebagai
    bukti dokumen apa yang dikirim ke klien pada waktu itu.
    """

    __tablename__ = "standard_cv_versions"
    __table_args__ = (UniqueConstraint("candidate_id", "seq", name="uq_cv_version_seq"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    intake_id: Mapped[UUID | None] = mapped_column(ForeignKey("cv_intakes.id"))
    seq: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_for_placement_id: Mapped[UUID | None] = mapped_column(ForeignKey("placements.id"))
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantCvBranding(TenantMixin, Base):
    """Konfigurasi branding CV standar per tenant (PRD §10.3)."""

    __tablename__ = "tenant_cv_branding"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    accent_color: Mapped[str] = mapped_column(String(9), default="#37352F")
    footer_text: Mapped[str] = mapped_column(String(255), default="")
    show_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    logo_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
