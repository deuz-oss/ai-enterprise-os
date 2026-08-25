import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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
from app.core.tenancy import TenantMixin


class GroupType(str, enum.Enum):
    """Kelompok akun ala Accurate — menentukan penempatan laporan."""

    aset_lancar = "aset_lancar"
    aset_tetap = "aset_tetap"
    liabilitas_pendek = "liabilitas_pendek"
    liabilitas_panjang = "liabilitas_panjang"
    ekuitas = "ekuitas"
    pendapatan = "pendapatan"
    hpp = "hpp"
    beban_usaha = "beban_usaha"
    beban_lain = "beban_lain"
    pendapatan_lain = "pendapatan_lain"


class Account(TenantMixin, Base):
    """Bagan akun dinamis per tenant (PRD §8.1).

    Saldo TIDAK disimpan — selalu dihitung dari jurnal (single source of
    truth). Akun yang sudah termutasi tidak boleh dihapus.
    """

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_account_tenant_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_code: Mapped[str | None] = mapped_column(String(20))
    group_type: Mapped[GroupType] = mapped_column(
        Enum(GroupType, native_enum=False, length=50),
        default=GroupType.aset_lancar,
        index=True,
    )
    normal_balance: Mapped[str] = mapped_column(String(10), default="debit")  # debit|kredit
    is_cash_bank: Mapped[bool] = mapped_column(Boolean, default=False)
    is_control_ar_ap: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountingPeriod(TenantMixin, Base):
    """Periode bulanan; baris hanya dibuat saat ditutup (lock). Tanpa baris = open."""

    __tablename__ = "accounting_periods"
    __table_args__ = (UniqueConstraint("tenant_id", "year", "month", name="uq_period_month"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer)
    closed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(500))


class JournalEntryStatus(str, enum.Enum):
    memorial = "memorial"  # draft
    posted = "posted"


class JournalEntry(TenantMixin, Base):
    """Jurnal umum; memorial → posted. Total debit wajib = total kredit.

    Auto-journal (PRD §8.3) mengisi event_code + source_ref_* dan bersifat
    idempoten: satu dokumen sumber → tepat satu jurnal per event.
    """

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "event_code", "source_ref_type", "source_ref_id", name="uq_journal_source_event"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    description: Mapped[str] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[JournalEntryStatus] = mapped_column(
        Enum(JournalEntryStatus, native_enum=False, length=50),
        default=JournalEntryStatus.posted,
        index=True,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Mesin auto-journal
    event_code: Mapped[str | None] = mapped_column(String(50), index=True)
    source_ref_type: Mapped[str | None] = mapped_column(String(50))
    source_ref_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.account_code",
        lazy="joined",
    )


class JournalLine(TenantMixin, Base):
    __tablename__ = "journal_lines"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_code: Mapped[str] = mapped_column(String(20), index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id"), default=None, index=True
    )
    debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Dimensi analisis (PRD §8.6): laba rugi per kontrak/klien
    client_dim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id"), default=None, index=True
    )
    memo: Mapped[str | None] = mapped_column(String(200))

    entry = relationship("JournalEntry", back_populates="lines")


class JournalRule(TenantMixin, Base):
    """Config mesin auto-journal (PRD §8.3): event aktif/tidak per tenant."""

    __tablename__ = "journal_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "event_code", name="uq_rule_tenant_event"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_code: Mapped[str] = mapped_column(String(50), index=True)
    debit_account_code: Mapped[str] = mapped_column(String(20))
    credit_account_code: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
