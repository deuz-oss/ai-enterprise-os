import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class AttendanceStatus(str, enum.Enum):
    hadir = "hadir"
    terlambat = "terlambat"
    izin = "izin"
    sakit = "sakit"
    cuti = "cuti"
    alpa = "alpa"
    libur = "libur"
    dinas_luar = "dinas_luar"


class AttendanceSource(str, enum.Enum):
    manual = "manual"
    impor = "impor"
    mobile = "mobile"
    ess = "ess"  # dibuat otomatis dari cuti/izin yang disetujui di ESS


class AttendanceRecord(TenantMixin, Base):
    """Absensi harian satu karyawan (Fase 8).

    Satu baris per karyawan per tanggal. Sumber data: input manual HR/Ops,
    impor CSV mesin fingerprint, mobile GPS+selfie (menyusul), dan otomatis
    dari pengajuan cuti/izin ESS yang disetujui.

    `AttendanceSummary` bulanan adalah artefak agregasi dari tabel ini —
    bukan tempat input.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_attendance_record_day"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, length=50),
        default=AttendanceStatus.hadir,
        index=True,
    )
    clock_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    overtime_hours: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource, native_enum=False, length=50),
        default=AttendanceSource.manual,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", lazy="joined")
