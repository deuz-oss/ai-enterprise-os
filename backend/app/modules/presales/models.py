import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin
from app.modules.auth.models import User


class LeadStage(str, enum.Enum):
    lead = "lead"
    contact = "kontak"
    presentation = "presentasi"
    quotation = "penawaran"
    negotiation = "negosiasi"
    won = "deal"
    lost = "gagal"


class ActivityType(str, enum.Enum):
    call = "telepon"
    meeting = "meeting"
    email = "email"
    note = "catatan"


class QuotationTemplate(TenantMixin, Base):
    """Fase 20 item 2 — template visual quotation (§field_schema JSON: daftar
    {key,label,type} yang diisi user saat bikin quotation baru). Rendering
    generik-nya ada di `presales/rendering.py::render_document_pdf`, dipakai
    ulang untuk Agreement (item 3) dan dokumen Job Order (Fase 21 item 4) --
    tiap jenis dokumen tetap punya tabel template sendiri (bukan satu tabel
    polymorphic lintas jenis), konsisten dengan pola modul lain di codebase
    ini yang menghindari abstraksi generik prematur."""

    __tablename__ = "quotation_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    field_schema: Mapped[str] = mapped_column(Text)  # JSON: [{key,label,type}, ...]
    footer_text: Mapped[str | None] = mapped_column(String(255))
    accent_color: Mapped[str] = mapped_column(String(9), default="#0f172a")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class QuotationStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    accepted_by_client = "accepted_by_client"
    expired = "expired"


class Quotation(TenantMixin, Base):
    """Fase 20 item 2. State machine: draft -> pending_approval ->
    approved/rejected -> sent -> accepted_by_client/expired. Approval
    single-level (admin/management mana pun -- lihat `service.decide_quotation`,
    pola sama dengan PR tanpa rantai configured di `finance/service.py`)."""

    __tablename__ = "quotations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("quotation_templates.id"))
    field_values: Mapped[str] = mapped_column(Text)  # JSON dict {field_key: value}
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus, native_enum=False, length=30),
        default=QuotationStatus.draft,
        index=True,
    )
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    rejection_note: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    object_key: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lead: Mapped["Lead"] = relationship()
    template: Mapped[QuotationTemplate] = relationship()


class AgreementTemplate(TenantMixin, Base):
    """Fase 20 item 3 — template visual Agreement, sama pola dengan
    `QuotationTemplate` (tabel sendiri per jenis dokumen, bukan polymorphic)."""

    __tablename__ = "agreement_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    field_schema: Mapped[str] = mapped_column(Text)  # JSON: [{key,label,type}, ...]
    footer_text: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgreementStatus(str, enum.Enum):
    draft = "draft"
    internal_review = "internal_review"
    approved = "approved"
    sent = "sent"
    signed = "signed"
    declined = "declined"
    expired = "expired"


class Agreement(TenantMixin, Base):
    """Fase 20 item 3. State machine: draft -> internal_review ->
    approved/declined -> sent -> signed/declined (lewat esign, item 4).
    `internal_review` sengaja dipisah dari `pending_approval` Quotation --
    nama beda, mekanisme approval-nya identik (lihat `service.decide_agreement`,
    disalin dari `service.decide_quotation`) -- klausul legal butuh review
    manusia sebelum dikirim, beda dari Quotation yang tidak butuh ini."""

    __tablename__ = "agreements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("agreement_templates.id"))
    field_values: Mapped[str] = mapped_column(Text)  # JSON dict {field_key: value}
    status: Mapped[AgreementStatus] = mapped_column(
        Enum(AgreementStatus, native_enum=False, length=30),
        default=AgreementStatus.draft,
        index=True,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    review_note: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    object_key: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lead: Mapped["Lead"] = relationship()
    template: Mapped[AgreementTemplate] = relationship()


class Company(TenantMixin, Base):
    """Fase 20: perusahaan calon klien — dulunya field bebas `Lead.company_name`,
    dipecah supaya satu company bisa punya banyak `Contact` (procurement, HR,
    trade marketing, dst.), bukan satu PIC tunggal tertanam di Lead."""

    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="Contact.created_at"
    )


class Contact(TenantMixin, Base):
    """PIC per company — banyak per company (Fase 20 item 1)."""

    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="contacts")


class Lead(TenantMixin, Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    estimated_headcount: Mapped[int | None] = mapped_column(default=None)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(16, 2), default=None)
    stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, native_enum=False, length=50), default=LeadStage.lead, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship()
    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadActivity.created_at"
    )
    owner: Mapped["User | None"] = relationship()

    # "Pemilik deal" -- kartu Kanban Pipeline (component-implementation-spec.md
    # §1.8). `owner_id` sudah ada sejak awal, properti ini baru dipakai sejak
    # LeadOut mengeksposnya (Fase 28 redesign).
    @property
    def owner_name(self) -> str | None:
        return self.owner.full_name if self.owner else None

    # ---- Kompatibilitas mundur (Fase 20 refactor, 2026-09-04) ----
    # `company_name`/`contact_*` dulunya kolom tertanam di Lead. Sekarang
    # sumber kebenarannya Company/Contact, tapi consumer lama (LeadOut,
    # `clients.service.convert_lead_to_client`, frontend Leads.tsx) masih
    # baca field ini langsung -- properti di bawah menjaga API/behaviour
    # lama tetap jalan tanpa sentuh pemanggilnya satu-satu.
    @property
    def company_name(self) -> str:
        return self.company.name if self.company else ""

    @property
    def industry(self) -> str | None:
        return self.company.industry if self.company else None

    @property
    def primary_contact(self) -> "Contact | None":
        if not self.company or not self.company.contacts:
            return None
        return next((c for c in self.company.contacts if c.is_primary), self.company.contacts[0])

    @property
    def contact_name(self) -> str | None:
        contact = self.primary_contact
        return contact.name if contact else None

    @property
    def contact_phone(self) -> str | None:
        contact = self.primary_contact
        return contact.phone if contact else None

    @property
    def contact_email(self) -> str | None:
        contact = self.primary_contact
        return contact.email if contact else None


class LeadActivity(TenantMixin, Base):
    __tablename__ = "lead_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, native_enum=False, length=50), default=ActivityType.note
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="activities")
