from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JournalEntry(Base):
    """Satu transaksi jurnal umum; total debit harus = total kredit."""

    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    description: Mapped[str] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.account_code",
        lazy="joined",
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_code: Mapped[str] = mapped_column(String(20), index=True)
    debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    entry = relationship("JournalEntry", back_populates="lines")
