import enum
import json
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class ScreeningVerdict(str, enum.Enum):
    recommended = "direkomendasikan"
    consider = "dipertimbangkan"
    reject = "tidak_direkomendasikan"


class AIScreening(TenantMixin, Base):
    """Hasil penilaian AI atas kandidat (screening CV / matching job order)."""

    __tablename__ = "ai_screenings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_orders.id"), nullable=True, index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[ScreeningVerdict] = mapped_column(
        Enum(ScreeningVerdict, native_enum=False, length=50)
    )
    summary: Mapped[str] = mapped_column(Text)
    # Disimpan sebagai teks JSON berisi list string.
    strengths_json: Mapped[str] = mapped_column(Text, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", lazy="joined")
    job_order = relationship("JobOrder", lazy="joined")

    @property
    def strengths(self) -> list[str]:
        return _load_list(self.strengths_json)

    @property
    def risks(self) -> list[str]:
        return _load_list(self.risks_json)


class AIDocumentChunk(TenantMixin, Base):
    """Potongan teks dokumen + vektor embedding untuk RAG Q&A kontrak."""

    __tablename__ = "ai_document_chunks"
    __table_args__ = (UniqueConstraint("source_id", "chunk_index", name="uq_chunk_source_idx"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50), default="employment_contract")
    source_id: Mapped[UUID] = mapped_column(index=True)
    employee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding_json: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data] if isinstance(data, list) else []
