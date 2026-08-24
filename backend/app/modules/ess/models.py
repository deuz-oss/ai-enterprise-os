import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class LeaveType(str, enum.Enum):
    annual = "cuti_tahunan"
    permission = "izin"
    sick = "sakit"
    unpaid = "cuti_tak_berbayar"


class LeaveStatus(str, enum.Enum):
    pending = "menunggu"
    approved = "disetujui"
    rejected = "ditolak"
    cancelled = "dibatalkan"


class LeaveRequest(TenantMixin, Base):
    """Pengajuan cuti/izin karyawan dari portal self-service.

    Alur: karyawan ajukan (pending) → HR setujui/tolak; karyawan boleh
    membatalkan sendiri selama masih pending.
    """

    __tablename__ = "leave_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, native_enum=False, length=50), default=LeaveType.annual
    )
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, native_enum=False, length=50),
        default=LeaveStatus.pending,
        index=True,
    )
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", lazy="joined")


class LeaveBalance(TenantMixin, Base):
    """Jatah cuti tahunan satu karyawan per periode tahun.

    Hanya pengajuan berjenis `cuti_tahunan` yang memotong kuota; izin,
    sakit, dan cuti tak berbayar bebas kuota. Tanpa baris balance untuk
    tahun terkait, approval cuti tidak dibatasi (opt-in oleh HR).
    """

    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "year", name="uq_leave_balance_period"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    used_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
