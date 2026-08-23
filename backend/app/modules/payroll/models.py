import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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


class PayrollRunStatus(str, enum.Enum):
    draft = "draft"
    final = "final"


class AttendanceSummary(Base):
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

    employee = relationship("Employee", lazy="joined")


class PayrollRun(Base):
    """Satu proses payrol untuk periode bulanan tertentu."""

    __tablename__ = "payroll_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[PayrollRunStatus] = mapped_column(
        Enum(PayrollRunStatus, native_enum=False, length=50),
        default=PayrollRunStatus.draft,
        index=True,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    slips: Mapped[list["Payslip"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Payslip(Base):
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
    employee = relationship("Employee", lazy="joined")
