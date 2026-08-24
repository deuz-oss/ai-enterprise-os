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
from app.core.tenancy import TenantMixin


class EmployeeStatus(str, enum.Enum):
    active = "aktif"
    resigned = "resign"


class MaritalStatus(str, enum.Enum):
    """Untuk perhitungan PPh 21: `tk` = tidak kawin, `k` = kawin."""

    single = "tk"
    married = "k"


class ContractSignStatus(str, enum.Enum):
    waiting = "menunggu_ttd"
    signed = "ditandatangani"


class HrDocumentType(str, enum.Enum):
    ktp = "ktp"
    npwp = "npwp"
    bpjs_kesehatan = "bpjs_kesehatan"
    bpjs_ketenagakerjaan = "bpjs_ketenagakerjaan"
    other = "lainnya"


class Employee(TenantMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("tenant_id", "employee_no", name="uq_employee_tenant_no"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Pintu masuk utama data karyawan adalah placement (Fase 1); boleh kosong
    # untuk karyawan lama yang diinput manual saat migrasi data awal.
    placement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("placements.id"), default=None, index=True
    )
    employee_no: Mapped[str] = mapped_column(String(50), index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    ktp_no: Mapped[str | None] = mapped_column(String(50))
    npwp_no: Mapped[str | None] = mapped_column(String(50))
    bpjs_kesehatan_no: Mapped[str | None] = mapped_column(String(50))
    bpjs_ketenagakerjaan_no: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(60))
    address: Mapped[str | None] = mapped_column(String(500))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account: Mapped[str | None] = mapped_column(String(100))
    join_date: Mapped[date | None] = mapped_column(Date, default=None)
    marital_status: Mapped[MaritalStatus | None] = mapped_column(
        Enum(MaritalStatus, native_enum=False, length=50), default=None
    )
    dependents: Mapped[int] = mapped_column(Integer, default=0)
    # Gaji pokok bulanan jadi dasar payrol (Fase 3); boleh diisi manual.
    base_salary: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Kelas risiko JKK BPJS Ketenagakerjaan (I–V); kosong = default modul bpjs.
    jkk_risk_category: Mapped[int | None] = mapped_column(Integer, default=None)
    # Akun login self-service (role karyawan) — dibuat oleh HR, opsional.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None, unique=True)
    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, native_enum=False, length=50),
        default=EmployeeStatus.active,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contracts: Mapped[list["EmploymentContract"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmploymentContract.start_date",
    )
    documents: Mapped[list["EmployeeDocument"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeDocument.uploaded_at",
    )


class EmploymentContract(TenantMixin, Base):
    """Kontrak kerja karyawan beserta status tanda tangan dan filenya."""

    __tablename__ = "employment_contracts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    contract_no: Mapped[str] = mapped_column(String(100), index=True)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    sign_status: Mapped[ContractSignStatus] = mapped_column(
        Enum(ContractSignStatus, native_enum=False, length=50),
        default=ContractSignStatus.waiting,
        index=True,
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    object_key: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship(back_populates="contracts")


class EmployeeDocument(TenantMixin, Base):
    """Dokumen HR (KTP, NPWP, BPJS, dll.) dengan versioning per jenis dokumen."""

    __tablename__ = "employee_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    document_type: Mapped[HrDocumentType] = mapped_column(
        Enum(HrDocumentType, native_enum=False, length=50), default=HrDocumentType.other
    )
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    object_key: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped[Employee] = relationship(back_populates="documents")
