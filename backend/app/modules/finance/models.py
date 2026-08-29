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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "terkirim"
    paid = "dibayar"
    cancelled = "dibatalkan"


class TaxInvoiceStatus(str, enum.Enum):
    """Status faktur pajak e-Faktur DJP — PRD v2.0 Finance."""

    belum_buat = "belum_buat"
    draft = "draft"
    menunggu_approval = "menunggu_approval"
    terkirim_djp = "terkirim_djp"
    approved = "approved"
    ditolak = "ditolak"
    dibatalkan = "dibatalkan"


class Invoice(TenantMixin, Base):
    """Tagihan bulanan ke klien: payrol + fee + PPN - PPh 23.

    `payroll_total` dihitung otomatis dari slip gaji karyawan milik klien
    (via placement → job order) pada periode terkait.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("client_id", "year", "month", name="uq_invoice_period"),
        UniqueConstraint("tenant_id", "invoice_no", name="uq_invoice_tenant_no"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    invoice_no: Mapped[str] = mapped_column(String(50), index=True)
    # Faktur pajak — PRD v3.0 lengkap (13 kolom, TEXT payload)
    tax_invoice_no: Mapped[str | None] = mapped_column(String(50), default=None, index=True)
    tax_invoice_status: Mapped[str | None] = mapped_column(String(30), default=None, index=True)
    tax_invoice_date: Mapped[date | None] = mapped_column(Date, default=None)
    lawan_npwp: Mapped[str | None] = mapped_column(String(20), default=None)
    lawan_nama: Mapped[str | None] = mapped_column(String(255), default=None)
    lawan_alamat: Mapped[str | None] = mapped_column(String(500), default=None)
    dpp_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    kode_transaksi: Mapped[str | None] = mapped_column(String(3), default=None)  # 01/04/09
    no_seri_faktur: Mapped[str | None] = mapped_column(
        String(30), default=None, index=True
    )  # 010.001-24.12345678
    faktur_pengganti_ref: Mapped[UUID | None] = mapped_column(
        ForeignKey("invoices.id"), default=None
    )
    faktur_status_detail: Mapped[str | None] = mapped_column(String(500), default=None)
    efaktur_nsr: Mapped[str | None] = mapped_column(String(100), default=None)  # NSFP DJP
    efaktur_qr_url: Mapped[str | None] = mapped_column(String(500), default=None)
    efaktur_payload: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # JSON DJP response — TEXT
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


class CashFlowEntry(TenantMixin, Base):
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


class PaymentRequestStatus(str, enum.Enum):
    submitted = "diajukan"
    waiting_superior = "menunggu_atasan"
    approved = "disetujui_atasan"
    executed = "dieksekusi"
    rejected = "ditolak"


class PaymentRequest(TenantMixin, Base):
    """Payment Request (PRD §7) — satu mesin untuk kedua jalur.

    DIAJUKAN (Ops utk proyek / HR utk internal)
      → MENUNGGU_ATASAN (rantai approval configurable per tenant, tahap demi tahap;
        tanpa rantai → management/admin mana pun memutus)
          ↘ DITOLAK (+catatan) → revisi → ajukan ulang
      → DISETUJUI_ATASAN
      → DIEKSEKUSI (Finance menjalankan pembayaran)
    Jurnal otomatis mengikuti mesin Fase 10.
    """

    __tablename__ = "payment_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "pr_number", name="uq_pr_tenant_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    pr_number: Mapped[str] = mapped_column(String(50), index=True)
    pr_type: Mapped[str] = mapped_column(
        String(20),
        default="internal",  # proyek | internal
    )
    payroll_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payroll_runs.id"), default=None, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[PaymentRequestStatus] = mapped_column(
        Enum(PaymentRequestStatus, native_enum=False, length=50),
        default=PaymentRequestStatus.submitted,
        index=True,
    )
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    executed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PRApprovalStep(TenantMixin, Base):
    """Satu tahap rantai approval Payment Request per tenant (PRD §7).

    Rantai diurutkan `seq` mulai 1; tiap tahap menunjuk satu user spesifik
    (`approver_id`) atau satu peran (`approver_role`) — salah satu wajib.
    Tanpa baris konfigurasi → perilaku legacy: management/admin mana pun
    dapat memutuskan.
    """

    __tablename__ = "pr_approval_steps"
    __table_args__ = (UniqueConstraint("tenant_id", "seq", name="uq_pr_step_tenant_seq"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    seq: Mapped[int] = mapped_column(Integer, index=True)
    approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    approver_role: Mapped[str | None] = mapped_column(String(50), default=None)


class PaymentRequestApproval(TenantMixin, Base):
    """Jejak keputusan per tahap rantai approval PR (audit trail)."""

    __tablename__ = "pr_approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_request_id: Mapped[UUID] = mapped_column(ForeignKey("payment_requests.id"), index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
