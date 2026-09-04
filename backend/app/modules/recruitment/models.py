import enum
import json
from datetime import date, datetime, time
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
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class JobOrderStatus(str, enum.Enum):
    open = "open"
    screening = "screening"
    interview = "interview_klien"
    offering = "offering"
    filled = "filled"
    closed = "closed"


class JobOrderBusinessStatus(str, enum.Enum):
    """Status bisnis JO level tinggi (PRD v3.1 Patch 3) — berbeda dari
    JobOrderStatus di atas yang melacak tahap pipeline rekrutmen internal."""

    open = "dibuka"
    on_hold = "ditahan"
    cancelled = "dibatalkan"
    filled = "terisi"


class CandidateStatus(str, enum.Enum):
    new = "baru"
    screening = "screening"
    interview = "interview"
    offered = "offered"
    placed = "placed"
    rejected = "gagal"
    archived = "arsip"


class PlacementStatus(str, enum.Enum):
    """Pipeline sourcing->onboarding per pasangan kandidat-JO (PRD v3.1 Patch 2).

    8 tahap baru ditambah SEBELUM `proposed` — makna proposed/accepted/
    onboarded/cancelled TIDAK berubah (tetap dipakai alur offering/esign
    yang sudah ada). `sourced` jadi status default baru saat Placement
    dibuat (sebelumnya `proposed`) — Placement sekarang dibuat sejak momen
    kandidat ditautkan ke JO (sourcing), bukan baru saat siap ditawari.
    """

    sourced = "disourcing"
    screening = "screening"
    interview_internal = "interview_rekruter"
    submitted = "disubmit"
    sent_to_client = "dikirim_ke_klien"
    client_screening = "screening_klien"
    interview_client = "interview_klien"
    ojt = "ojt"
    proposed = "diusulkan"
    accepted = "disetujui_klien"
    # Fase 24 -- disisipkan di antara accepted & onboarded, mengikuti istilah
    # MYOHRIS "Hired": klien sudah setuju tapi belum resmi onboarding sistem.
    hired = "hired"
    onboarded = "onboarded"
    rejected = "gagal"
    cancelled = "dibatalkan"


class InterviewStatus(str, enum.Enum):
    scheduled = "terjadwal"
    done = "selesai"
    no_show = "tidak_hadir"
    cancelled = "dibatalkan"


class InterviewType(str, enum.Enum):
    """Interview rekruter internal vs interview user oleh klien (PRD v3.1 Patch 2)."""

    internal = "internal"
    klien = "klien"


class InterviewSchedule(TenantMixin, Base):
    """Jadwal interview — PRD v3.0 Talent Cloud."""

    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID] = mapped_column(ForeignKey("job_orders.id"), index=True)
    interviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(255), default=None)
    meeting_url: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, native_enum=False, length=50),
        default=InterviewStatus.scheduled,
        index=True,
    )
    interview_type: Mapped[InterviewType] = mapped_column(
        Enum(InterviewType, native_enum=False, length=20),
        default=InterviewType.internal,
        index=True,
    )
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    score: Mapped[int | None] = mapped_column(Integer, default=None)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobOrderTemplate(TenantMixin, Base):
    """Fase 21 item 4 — template dokumen Job Order, pola generate identik
    Quotation/Agreement (Fase 20): render lewat `presales.rendering.
    render_document_pdf`, simpan lewat `store_generated_document`.

    SENGAJA lebih ramping dari QuotationTemplate/AgreementTemplate --
    TIDAK punya `field_schema`. Isi dokumen JO 100% deterministik dari
    field JobOrder sendiri (title, area, benefits, working_days/hours,
    dst — lihat `generate_job_order_document`), tidak ada input bebas per
    dokumen seperti Quotation/Agreement. Template di sini murni kontrol
    presentasi (footer, warna aksen) -- nambah field_schema yang tidak
    pernah dipakai cuma kompleksitas tanpa manfaat."""

    __tablename__ = "job_order_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    footer_text: Mapped[str | None] = mapped_column(String(255))
    accent_color: Mapped[str] = mapped_column(String(9), default="#0f172a")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JobOrder(TenantMixin, Base):
    __tablename__ = "job_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_id", name="uq_job_order_tenant_request_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    headcount: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    salary_max: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[JobOrderStatus] = mapped_column(
        # SENGAJA TANPA values_callable, JANGAN ditambah tanpa migrasi data
        # dulu. Sempat dicoba (2026-09-02) mengikuti pola business_status di
        # bawah karena JobOrderStatus.interview="interview_klien" (nama !=
        # nilai) terlihat seperti kelas bug yang sama -- ternyata SALAH:
        # baris JobOrder yang sudah ada di Postgres tersimpan berbasis NAMA
        # ("interview", bukan "interview_klien"), karena itu memang
        # perilaku default SQLAlchemy Enum(native_enum=False) selama ini.
        # Menambah values_callable membuat baris lama itu gagal dibaca
        # (`LookupError: 'interview' is not among the defined enum values`)
        # -- ketahuan langsung lewat verifikasi Docker+Postgres nyata,
        # sebelum sempat commit. Kalau suatu saat benar-benar mau
        # values_callable di sini, WAJIB dibarengi migrasi UPDATE data
        # (name->value) di baris lama dulu, bukan cuma ubah kolom model.
        Enum(JobOrderStatus, native_enum=False, length=50),
        default=JobOrderStatus.open,
        index=True,
    )
    # PRD v3.1 Patch 3 — field operasional tambahan
    request_id: Mapped[str | None] = mapped_column(String(50), index=True)
    request_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    area: Mapped[str | None] = mapped_column(String(120))
    contract_duration_months: Mapped[int | None] = mapped_column(Integer)
    gross_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    business_status: Mapped[JobOrderBusinessStatus] = mapped_column(
        # values_callable wajib: nama anggota enum ini beda dari nilai
        # string-nya (open="dibuka", dst), dan create/update job order lewat
        # payload.model_dump() yang "membuka" enum jadi nilai mentah sebelum
        # disimpan -- tanpa ini SQLAlchemy simpan/cari berdasar NAMA anggota,
        # bentrok dengan nilai yang sebenarnya ada di kolom -> LookupError
        # saat baca baris manapun.
        Enum(
            JobOrderBusinessStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=JobOrderBusinessStatus.open,
        index=True,
    )
    # PRD v3.1 Patch 2 — kondisional per JO, bukan per Client
    requires_ojt: Mapped[bool] = mapped_column(Boolean, default=False)
    # PRD v3.1 Patch 3b — dokumen Job Order/Manpower Requisition sumber (opsional)
    source_document_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    source_document_file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    # PRD v3.1 Patch 5 — Job Portal: opt-in publik per JO
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nama klien tersamar utk lowongan publik — TIDAK PERNAH fallback ke
    # client.name asli (temuan dari dokumen JO sungguhan: klien bisa minta
    # identitasnya disembunyikan dari iklan lowongan publik).
    public_client_label: Mapped[str | None] = mapped_column(String(255), default=None)
    screening_questions_json: Mapped[str | None] = mapped_column(Text, default=None)
    # Fase 21 item 1 — field terstruktur benefit & jam kerja, dulunya numpang
    # di teks bebas description/requirements. benefits: JSON list terstruktur
    # (bukan teks bebas) supaya bisa di-auto-fill ke dokumen JO/offering
    # letter nanti. working_days: JSON list hari kerja (mis. ["senin",...]).
    benefits_json: Mapped[str | None] = mapped_column(Text, default=None)
    working_days_json: Mapped[str | None] = mapped_column(Text, default=None)
    working_hours_start: Mapped[time | None] = mapped_column(Time, default=None)
    working_hours_end: Mapped[time | None] = mapped_column(Time, default=None)
    # Fase 21 item 4 — dokumen JO ter-generate dari template, BEDA dari
    # source_document_object_key di atas (itu untuk *upload* dokumen JO dari
    # klien; ini untuk *generate* keluar dari sistem berdasar field JO sendiri).
    generated_document_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    generated_document_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Fase 24 -- field tambahan hasil audit MYOHRIS, mayoritas kolom datar.
    # `frequency` SENGAJA TIDAK diimplementasikan (keputusan eksplisit PRD).
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    office_address: Mapped[str | None] = mapped_column(String(500), default=None)
    experience_level: Mapped[str | None] = mapped_column(String(120), default=None)
    # "Full Time"/"Part Time" -- beda dari contract_duration_months di atas.
    contract_detail: Mapped[str | None] = mapped_column(String(50), default=None)
    industry: Mapped[str | None] = mapped_column(String(120), default=None)
    # `title` di atas tetap teks bebas; position+level klasifikasi terstruktur.
    position: Mapped[str | None] = mapped_column(String(120), default=None)
    level: Mapped[str | None] = mapped_column(String(120), default=None)
    package_detail: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", lazy="selectin")
    placements: Mapped[list["Placement"]] = relationship(back_populates="job_order")

    @property
    def benefits(self) -> list[str]:
        if not self.benefits_json:
            return []
        try:
            parsed = json.loads(self.benefits_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @property
    def working_days(self) -> list[str]:
        if not self.working_days_json:
            return []
        try:
            parsed = json.loads(self.working_days_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @property
    def is_stale(self) -> bool:
        """Alert: JO masih dibuka DAN request_date >= 30 hari lalu (PRD v3.1 Patch 3)."""
        if self.business_status != JobOrderBusinessStatus.open:
            return False
        return (date.today() - self.request_date).days >= 30

    @property
    def has_source_document(self) -> bool:
        return self.source_document_object_key is not None

    @property
    def has_generated_document(self) -> bool:
        return self.generated_document_object_key is not None

    @property
    def screening_questions(self) -> list[dict]:
        if not self.screening_questions_json:
            return []
        try:
            parsed = json.loads(self.screening_questions_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []


class Candidate(TenantMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    education: Mapped[str | None] = mapped_column(String(255))
    experience_years: Mapped[int | None] = mapped_column(Integer, default=0)
    current_company: Mapped[str | None] = mapped_column(String(255))
    expected_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    # Teks bebas, ditokenisasi ad hoc (`.split()`) saat matching -- TIDAK
    # diubah oleh Fase 24, biar logika matching yang sudah jalan tak kesentuh.
    # `skills_json`/`skills_list` di bawah adalah field terstruktur baru,
    # terpisah, utk filter/tampilan (populasi lewat UI baru ke depan).
    skills: Mapped[str | None] = mapped_column(Text)
    skills_json: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str | None] = mapped_column(String(120))
    cv_object_key: Mapped[str | None] = mapped_column(String(500))
    cv_file_name: Mapped[str | None] = mapped_column(String(255))
    # Foto kandidat untuk CV standar (ditampilkan bila branding tenant mengizinkan)
    photo_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, native_enum=False, length=50),
        default=CandidateStatus.new,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # Fase 24 -- field tambahan hasil audit MYOHRIS. `industry`/
    # `current_department` SENGAJA TIDAK diimplementasikan (keputusan
    # eksplisit PRD).
    reference: Mapped[str | None] = mapped_column(String(50), index=True)
    gender: Mapped[str | None] = mapped_column(String(20), default=None)
    current_position: Mapped[str | None] = mapped_column(String(255), default=None)
    birthdate: Mapped[date | None] = mapped_column(Date, default=None)
    birthplace: Mapped[str | None] = mapped_column(String(120), default=None)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    ktp_no: Mapped[str | None] = mapped_column(String(50), default=None)
    marital_status: Mapped[str | None] = mapped_column(String(20), default=None)
    blood_type: Mapped[str | None] = mapped_column(String(5), default=None)
    religion: Mapped[str | None] = mapped_column(String(50), default=None)
    languages_json: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    position_pool: Mapped[str | None] = mapped_column(String(255), default=None)
    job_level: Mapped[str | None] = mapped_column(String(120), default=None)
    school: Mapped[str | None] = mapped_column(String(255), default=None)
    # `education` di atas tetap teks bebas gabungan; education_level terpisah.
    education_level: Mapped[str | None] = mapped_column(String(120), default=None)
    # Fase 27 -- jalur sourcing ketiga (referral), di samping Job Portal &
    # Talent Pool. Nullable: mayoritas kandidat tetap tanpa referral.
    referred_by_employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id"), default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    experiences: Mapped[list["CandidateExperience"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateExperience.start_date.desc()",
    )

    @property
    def skills_list(self) -> list[str]:
        if not self.skills_json:
            return []
        try:
            parsed = json.loads(self.skills_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @property
    def languages(self) -> list[str]:
        if not self.languages_json:
            return []
        try:
            parsed = json.loads(self.languages_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []


class CandidateExperience(TenantMixin, Base):
    """Riwayat pengalaman per posisi -- Fase 24, mengganti gap `experience_years`
    yang sebelumnya cuma angka total tanpa rincian per posisi."""

    __tablename__ = "candidate_experiences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    company: Mapped[str] = mapped_column(String(255))
    position: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped[Candidate] = relationship(back_populates="experiences")


class Placement(TenantMixin, Base):
    __tablename__ = "placements"
    __table_args__ = (UniqueConstraint("candidate_id", "job_order_id", name="uq_candidate_jo"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_order_id: Mapped[UUID] = mapped_column(ForeignKey("job_orders.id"), index=True)
    offered_salary: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[PlacementStatus] = mapped_column(
        # PRD v3.1 Patch 2: default sekarang `sourced` (bukan `proposed`) —
        # Placement dibuat sejak momen sourcing, bukan cuma saat siap ditawari.
        Enum(PlacementStatus, native_enum=False, length=50),
        default=PlacementStatus.sourced,
    )
    # PRD v3.1 Patch 2 — OJT kondisional, dilewati kalau JobOrder.requires_ojt=False
    ojt_start_date: Mapped[date | None] = mapped_column(Date, default=None)
    ojt_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    # PRD v3.0 §4 aksi "Offering": surat penawaran PDF dibrandingi + esign.
    offering_letter_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    offering_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Fase 21 item 2 — offering call sebagai aksi tercatat terpisah dari
    # offering letter+esign di atas (klien bisa pilih call saja, letter
    # saja, atau keduanya; sebelumnya cuma letter yang punya jejak).
    offering_call_done: Mapped[bool] = mapped_column(Boolean, default=False)
    offering_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # PRD v3.1 Patch 5 — Job Portal: NULL kalau sourcing dari Talent Pool
    # internal, terisi kalau kandidat apply sendiri lewat portal publik.
    application_token: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    screening_answers: Mapped[str | None] = mapped_column(Text, default=None)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", lazy="selectin")
    job_order = relationship("JobOrder", back_populates="placements", lazy="selectin")


class ReferralRewardStatus(str, enum.Enum):
    pending = "pending"
    eligible = "eligible"
    paid = "paid"
    cancelled = "cancelled"


class ReferralProgramSetting(TenantMixin, Base):
    """Fase 27 -- toggle on/off program referral per tenant (singleton).
    Konvensi "satu baris per tenant" sama seperti `TenantCvBranding`
    (talentpool/models.py) -- bukan tabel dengan banyak baris per tenant."""

    __tablename__ = "referral_program_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReferralReward(TenantMixin, Base):
    """Fase 27 -- insentif referral, satu baris per kandidat-yang-direferensikan
    yang berhasil placement. `eligible_at` = `placement.start_date` + 3 bulan,
    dihitung ulang tiap `start_date` berubah (lihat `recruitment/service.py`).
    Transisi pending->eligible dihitung on-the-fly lewat `is_eligible`
    (pola sama `JobOrder.is_stale`), BUKAN job terjadwal -- tidak ada
    infrastruktur scheduler di codebase ini."""

    __tablename__ = "referral_rewards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    placement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("placements.id"), default=None, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    eligible_at: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[ReferralRewardStatus] = mapped_column(
        Enum(ReferralRewardStatus, native_enum=False, length=20),
        default=ReferralRewardStatus.pending,
        index=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def is_eligible(self) -> bool:
        if self.status != ReferralRewardStatus.pending or self.eligible_at is None:
            return False
        return date.today() >= self.eligible_at
