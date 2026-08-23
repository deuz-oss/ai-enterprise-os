import enum
from datetime import date, datetime
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


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "terkirim"
    paid = "dibayar"
    cancelled = "dibatalkan"


class Invoice(Base):
    """Tagihan bulanan ke klien: payrol + fee + PPN - PPh 23.

    `payroll_total` dihitung otomatis dari slip gaji karyawan milik klien
    (via placement → job order) pada periode terkait.
    """

    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("client_id", "year", "month", name="uq_invoice_period"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    invoice_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    payroll_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    fee_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    ppn_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    ppn_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    pph23_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    pph23_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_due: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, length=50),
        default=InvoiceStatus.draft,
        index=True,
    )
    issued_date: Mapped[date | None] = mapped_column(Date, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", lazy="joined")


class CashFlowDirection(str, enum.Enum):
    inflow = "masuk"
    outflow = "keluar"


class CashFlowEntry(Base):
    """Catatan arus kas manual/otomatis untuk pemantauan likuiditas."""

    __tablename__ = "cash_flow_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    direction: Mapped[CashFlowDirection] = mapped_column(
        Enum(CashFlowDirection, native_enum=False, length=20), index=True
    )
    category: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
