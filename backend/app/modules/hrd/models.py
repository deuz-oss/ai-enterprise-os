import enum
import json
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class EmployeeStatus(str, enum.Enum):
    active = "aktif"
    resigned = "resign"


class EmploymentType(str, enum.Enum):
    """Jenis kepegawaian — menentukan jalur validasi absensi & payrol (Fase 8-9).

    internal  : karyawan kantor (divisi sendiri) → absensi divalidasi HR.
    eksternal : karyawan outsourcing yang ditempatkan di klien → divalidasi
                Operations/approval klien.
    """

    internal = "internal"
    eksternal = "eksternal"


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
    kartu_bpjs_kesehatan = "kartu_bpjs_kesehatan"
    kartu_bpjs_ketenagakerjaan = "kartu_bpjs_ketenagakerjaan"
    skck = "skck"
    other = "lainnya"


class WarningLetterType(str, enum.Enum):
    sp1 = "sp1"
    sp2 = "sp2"
    sp3 = "sp3"


class InsuranceProvider(str, enum.Enum):
    """Provider asuransi swasta (polis + kartu) — PRD v2.0 People & Ops."""

    prudential = "prudential"
    allianz = "allianz"
    axa = "axa"
    manulife = "manulife"
    bri_life = "bri_life"
    sinarmas = "sinarmas"
    other = "lainnya"


class InsuranceStatus(str, enum.Enum):
    aktif = "aktif"
    nonaktif = "nonaktif"
    menunggu = "menunggu"


class EmployeeInsurance(TenantMixin, Base):
    """Asuransi one-to-many per karyawan — PRD v3.0 Workforce Cloud."""

    __tablename__ = "employee_insurances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50), default="lainnya")
    policy_no: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="aktif")
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    valid_until: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    card_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    policy_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    # Kartu BPJS — PRD v3.0 + valid_until
    bpjs_kesehatan_card_key: Mapped[str | None] = mapped_column(String(500), default=None)
    bpjs_ketenagakerjaan_card_key: Mapped[str | None] = mapped_column(String(500), default=None)
    bpjs_kesehatan_status: Mapped[str | None] = mapped_column(String(20), default=None)
    bpjs_ketenagakerjaan_status: Mapped[str | None] = mapped_column(String(20), default=None)
    bpjs_kesehatan_valid_until: Mapped[date | None] = mapped_column(Date, default=None)
    bpjs_ketenagakerjaan_valid_until: Mapped[date | None] = mapped_column(Date, default=None)
    # Asuransi swasta — polis + kartu (PRD v2.0)
    insurance_provider: Mapped[str | None] = mapped_column(String(50), default=None)
    insurance_policy_no: Mapped[str | None] = mapped_column(String(100), default=None)
    insurance_status: Mapped[str | None] = mapped_column(String(20), default=None)
    insurance_card_key: Mapped[str | None] = mapped_column(String(500), default=None)
    insurance_policy_key: Mapped[str | None] = mapped_column(String(500), default=None)
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
    # Jenis kepegawaian: menentukan jalur validasi absensi & payrol (Fase 8-9).
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType, native_enum=False, length=50),
        default=EmploymentType.eksternal,
        server_default="eksternal",
    )
    # Akun login self-service (role karyawan) — dibuat oleh HR, opsional.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None, unique=True)
    # Fase 27 -- kode referral unik per tenant, auto-generated saat karyawan
    # dibuat (pola sama `employee_no`, lihat `_generate_employee_no`).
    referral_code: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, native_enum=False, length=50),
        default=EmployeeStatus.active,
        index=True,
    )
    # Fase 26 -- Employee Detail: grade & level 2 konsep hierarki terpisah
    # (bukan satu field dipecah), belum ada padanan sebelumnya.
    grade: Mapped[str | None] = mapped_column(String(50), default=None)
    level: Mapped[str | None] = mapped_column(String(50), default=None)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), default=None)
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(100), default=None)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(60), default=None)
    # `address` di atas tetap alamat flat lama (legacy/fallback) -- ini
    # alamat terstruktur baru, KTP vs domisili dipisah (JSON blob per pola
    # `JobOrder.benefits_json`): {province, city, district, postal_code, detail}.
    citizen_address_json: Mapped[str | None] = mapped_column(Text, default=None)
    residential_address_json: Mapped[str | None] = mapped_column(Text, default=None)
    # Kunci periode payroll level karyawan -- cegah edit slip lebih lanjut
    # setelah dikunci (lihat guard di payroll/service.py).
    payroll_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    payroll_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
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
    warning_letters: Mapped[list["WarningLetter"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="WarningLetter.issued_at",
    )
    movements: Mapped[list["EmployeeMovement"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeMovement.effective_date",
    )
    vaccine_records: Mapped[list["VaccineRecord"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="VaccineRecord.vaccinated_at",
    )

    @property
    def citizen_address(self) -> dict:
        if not self.citizen_address_json:
            return {}
        try:
            parsed = json.loads(self.citizen_address_json)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @property
    def residential_address(self) -> dict:
        if not self.residential_address_json:
            return {}
        try:
            parsed = json.loads(self.residential_address_json)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}


class EmploymentContractTemplate(TenantMixin, Base):
    """Fase 25 -- template generator kontrak karyawan, tabel SENDIRI dari
    `presales.AgreementTemplate` (keputusan eksplisit: dua modul terpisah
    meski pola field_schema JSON + rendering-nya sama), mengikuti konvensi
    satu tabel per jenis dokumen yang sudah dipakai QuotationTemplate/
    AgreementTemplate/JobOrderTemplate."""

    __tablename__ = "employment_contract_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    field_schema: Mapped[str] = mapped_column(Text)  # JSON: [{key,label,type,list_style?}, ...]
    footer_text: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmploymentContract(TenantMixin, Base):
    """Kontrak kerja karyawan beserta status tanda tangan dan filenya."""

    __tablename__ = "employment_contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_no", name="uq_contract_tenant_contract_no"),
    )

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
    # Fase 25 -- generator kontrak, nullable: kontrak lama/upload-manual
    # (tanpa template) tidak terdampak, tetap jalan seperti sebelumnya.
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employment_contract_templates.id"), default=None
    )
    field_values: Mapped[str | None] = mapped_column(Text, default=None)  # JSON dict
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship(back_populates="contracts")
    template: Mapped[EmploymentContractTemplate | None] = relationship()


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


class WarningLetter(TenantMixin, Base):
    """Surat Peringatan (SP1/SP2/SP3) karyawan -- Fase 23 butir 3.

    `valid_until` (lazimnya `issued_at` + 6 bulan, dihitung di service.py saat
    dibuat) dipakai `is_active` di bawah utk bedakan SP yang masih berlaku vs
    riwayat lama, pola sama seperti `JobOrder.is_stale` -- dihitung on-the-fly,
    bukan status tersimpan yang perlu disinkron oleh job terjadwal.
    """

    __tablename__ = "warning_letters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    letter_type: Mapped[WarningLetterType] = mapped_column(
        Enum(WarningLetterType, native_enum=False, length=20)
    )
    reason: Mapped[str] = mapped_column(String(2000))
    issued_at: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    mime_type: Mapped[str | None] = mapped_column(String(120), default=None)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    issued_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship(back_populates="warning_letters")

    @property
    def is_active(self) -> bool:
        if self.valid_until is None:
            return True
        return date.today() <= self.valid_until


class MovementType(str, enum.Enum):
    mutasi = "mutasi"
    promosi = "promosi"
    demosi = "demosi"
    other = "lainnya"


class EmployeeMovement(TenantMixin, Base):
    """Riwayat mutasi/promosi/demosi karyawan -- Fase 26 tab "Movements"
    Employee Detail, belum ada padanan sebelumnya di codebase ini."""

    __tablename__ = "employee_movements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, native_enum=False, length=20), default=MovementType.other
    )
    previous_grade: Mapped[str | None] = mapped_column(String(50), default=None)
    new_grade: Mapped[str | None] = mapped_column(String(50), default=None)
    previous_level: Mapped[str | None] = mapped_column(String(50), default=None)
    new_level: Mapped[str | None] = mapped_column(String(50), default=None)
    previous_division: Mapped[str | None] = mapped_column(String(120), default=None)
    new_division: Mapped[str | None] = mapped_column(String(120), default=None)
    previous_position: Mapped[str | None] = mapped_column(String(120), default=None)
    new_position: Mapped[str | None] = mapped_column(String(120), default=None)
    effective_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship(back_populates="movements")


class VaccineRecord(TenantMixin, Base):
    """Riwayat vaksinasi karyawan -- Fase 26, konsep baru."""

    __tablename__ = "vaccine_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    vaccine_name: Mapped[str] = mapped_column(String(120))
    dose_number: Mapped[int] = mapped_column(Integer, default=1)
    vaccinated_at: Mapped[date] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(255), default=None)
    object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship(back_populates="vaccine_records")
