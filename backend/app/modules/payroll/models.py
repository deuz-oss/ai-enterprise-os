import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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


class PayrollRunType(str, enum.Enum):
    internal = "internal"
    proyek = "proyek"


class PayrollRunStatus(str, enum.Enum):
    draft = "draft"
    submitted_to_client = "submitted_to_client"
    client_rejected = "client_rejected"
    client_approved = "client_approved"
    finance_processing = "finance_processing"
    final = "final"


class AttendanceSummary(TenantMixin, Base):
    """Rekap kehadiran + lembur bulanan per karyawan.

    Klien menyetujui lembur/kehadiran (approval) sebelum angkanya
    boleh dipakai dalam payrol.
    """

    __tablename__ = "attendance_summaries"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_attendance_period"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    present_days: Mapped[int] = mapped_column(Integer, default=0)
    overtime_hours: Mapped[int] = mapped_column(Integer, default=0)
    client_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", lazy="selectin")


class PayrollRun(TenantMixin, Base):
    """Satu proses payrol untuk periode bulanan tertentu.

    Fase 9 dua jalur:
    - internal : karyawan kantor; DRAFT → FINANCE_PROCESSING → FINALIZED.
    - proyek   : per klien per periode; DRAFT → SUBMITTED_TO_CLIENT →
                 CLIENT_APPROVED (atau REJECTED→DRAFT) → FINANCE_PROCESSING
                 → FINALIZED. Approval via link ber-token tanpa akun.
    """

    __tablename__ = "payroll_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    run_type: Mapped[PayrollRunType] = mapped_column(
        Enum(PayrollRunType, native_enum=False, length=50),
        default=PayrollRunType.internal,
        server_default="internal",
        index=True,
    )
    # Wajib untuk run proyek: payrol ditagihkan ke satu klien.
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id"), default=None, index=True
    )
    status: Mapped[PayrollRunStatus] = mapped_column(
        Enum(PayrollRunStatus, native_enum=False, length=50),
        default=PayrollRunStatus.draft,
        index=True,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Snapshot rate ber-versi untuk konsistensi historis (NFR §11)
    pph21_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bpjs_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    slips: Mapped[list["Payslip"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    client = relationship("Client", lazy="selectin")


class PayslipComponentType(str, enum.Enum):
    earnings = "earnings"  # pemasukan billable (masuk gross, ditagih ke klien)
    deduction = "deduction"  # potongan karyawan (mengurangi THP)
    passthrough = "passthrough"  # BPJS employer — bukan pendapatan, ditagih ke klien


class PayslipComponent(TenantMixin, Base):
    """Line-item Saltab (PRD §6): rincian komponen satu slip gaji.

    - `source=auto` dibangun mesin saat generate (prorata absensi & BPJS).
    - Override manual via grid Saltab mengubah amount + source=`manual`,
      tercatat di audit; agregat slip (gross/net) dihitung ulang dari sini.
    """

    __tablename__ = "payslip_components"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payslip_id: Mapped[UUID] = mapped_column(ForeignKey("payslips.id"), index=True)
    ctype: Mapped[PayslipComponentType] = mapped_column(
        Enum(PayslipComponentType, native_enum=False, length=50),
        default=PayslipComponentType.earnings,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    source: Mapped[str] = mapped_column(String(20), default="auto")
    notes: Mapped[str | None] = mapped_column(String(500))

    payslip = relationship("Payslip", back_populates="components")


class PayrollRunToken(TenantMixin, Base):
    """Token approval payrol proyek untuk klien (link tanpa akun).

    Token disimpan sebagai hash SHA-256; nilai mentah hanya tampil sekali
    saat HR/Ops membuat link. Satu token belum terpakai per run — membuat
    link baru mencabut yang lama.
    """

    __tablename__ = "payroll_run_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by_name: Mapped[str | None] = mapped_column(String(255))
    decision_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Payslip(TenantMixin, Base):
    """Slip gaji satu karyawan dalam satu payroll run."""

    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("run_id", "employee_id", name="uq_run_employee"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    base_salary: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    allowance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    overtime_hours: Mapped[int] = mapped_column(Integer, default=0)
    overtime_rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    overtime_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    gross: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    pph21_method: Mapped[str] = mapped_column(String(20), default="ter")
    tax_pph21: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run = relationship("PayrollRun", back_populates="slips")
    employee = relationship("Employee", lazy="selectin")
    components: Mapped[list["PayslipComponent"]] = relationship(
        back_populates="payslip",
        cascade="all, delete-orphan",
        order_by="PayslipComponent.ctype",
    )
