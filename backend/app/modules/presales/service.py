import csv
import io
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.presales.models import (
    ActivityType,
    Agreement,
    AgreementStatus,
    AgreementTemplate,
    Company,
    Contact,
    CustomFieldDefinition,
    CustomFieldOption,
    CustomFieldValue,
    FieldEntity,
    FieldType,
    Lead,
    LeadActivity,
    LeadContact,
    LeadStage,
    Quotation,
    QuotationStatus,
    QuotationTemplate,
    SavedLeadView,
    SuppressedContact,
)
from app.modules.presales.schemas import (
    AgreementCreate,
    AgreementTemplateCreate,
    AgreementTemplateUpdate,
    CompanyCreate,
    CompanyUpdate,
    ContactCreate,
    ContactUpdate,
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionUpdate,
    CustomFieldValueIn,
    FunnelStage,
    FunnelStats,
    LeadContactCreate,
    LeadContactUpdate,
    LeadCreate,
    LeadImportResultOut,
    LeadImportRowFailure,
    LeadUpdate,
    QuotationCreate,
    QuotationTemplateCreate,
    QuotationTemplateUpdate,
    SavedLeadViewCreate,
    SuppressedContactCreate,
)

logger = logging.getLogger(__name__)


def _get(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, parse_uuid(lead_id))
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead tidak ditemukan")
    return lead


def _get_company(db: Session, company_id: str) -> Company:
    company = db.get(Company, parse_uuid(company_id))
    if company is None:
        raise HTTPException(status_code=404, detail="Company tidak ditemukan")
    return company


def _get_contact(db: Session, contact_id: str) -> Contact:
    contact = db.get(Contact, parse_uuid(contact_id))
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact tidak ditemukan")
    return contact


# ---------------- Company & Contact (Fase 20 item 1) ----------------


def create_company(db: Session, payload: CompanyCreate) -> Company:
    company = Company(
        id=uuid4(),
        name=payload.name,
        industry=payload.industry,
        size=payload.size,
        source=payload.source,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def list_companies(
    db: Session, q: str | None = None, limit: int = 200, offset: int = 0
) -> tuple[list[Company], int]:
    stmt = select(Company).order_by(Company.created_at.desc())
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_company(db: Session, company_id: str) -> Company:
    return _get_company(db, company_id)


def update_company(db: Session, company_id: str, payload: CompanyUpdate) -> Company:
    company = _get_company(db, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


def add_contact(db: Session, company_id: str, payload: ContactCreate) -> Contact:
    company = _get_company(db, company_id)
    contact = Contact(id=uuid4(), company_id=company.id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def list_contacts(db: Session, company_id: str) -> list[Contact]:
    company = _get_company(db, company_id)
    return list(company.contacts)


def update_contact(db: Session, contact_id: str, payload: ContactUpdate) -> Contact:
    contact = _get_contact(db, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact_id: str) -> None:
    contact = _get_contact(db, contact_id)
    db.delete(contact)
    db.commit()


# ---------------- Quotation template (Fase 20 item 2) ----------------


def _get_quotation_template(db: Session, template_id: str) -> QuotationTemplate:
    tmpl = db.get(QuotationTemplate, parse_uuid(template_id))
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template quotation tidak ditemukan")
    return tmpl


def create_quotation_template(db: Session, payload: QuotationTemplateCreate) -> QuotationTemplate:
    tmpl = QuotationTemplate(
        id=uuid4(),
        name=payload.name,
        field_schema=json.dumps([f.model_dump() for f in payload.field_schema]),
        footer_text=payload.footer_text,
        accent_color=payload.accent_color,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def list_quotation_templates(db: Session, active_only: bool = False) -> list[QuotationTemplate]:
    stmt = select(QuotationTemplate).order_by(QuotationTemplate.created_at.desc())
    if active_only:
        stmt = stmt.where(QuotationTemplate.is_active.is_(True))
    return list(db.execute(stmt).scalars())


def get_quotation_template(db: Session, template_id: str) -> QuotationTemplate:
    return _get_quotation_template(db, template_id)


def update_quotation_template(
    db: Session, template_id: str, payload: QuotationTemplateUpdate
) -> QuotationTemplate:
    tmpl = _get_quotation_template(db, template_id)
    data = payload.model_dump(exclude_unset=True)
    if "field_schema" in data:
        data["field_schema"] = json.dumps(data["field_schema"])
    for field, value in data.items():
        setattr(tmpl, field, value)
    db.commit()
    db.refresh(tmpl)
    return tmpl


# ---------------- Quotation (Fase 20 item 2) ----------------


def _get_quotation(db: Session, quotation_id: str) -> Quotation:
    quotation = db.get(Quotation, parse_uuid(quotation_id))
    if quotation is None:
        raise HTTPException(status_code=404, detail="Quotation tidak ditemukan")
    return quotation


def create_quotation(db: Session, *, user, payload: QuotationCreate) -> Quotation:
    lead = _get(db, str(payload.lead_id))
    template = _get_quotation_template(db, str(payload.template_id))

    quotation = Quotation(
        id=uuid4(),
        lead_id=lead.id,
        template_id=template.id,
        field_values=json.dumps(payload.field_values),
        status=QuotationStatus.draft,
        created_by=user.id,
    )
    db.add(quotation)
    # Lead otomatis maju ke tahap "penawaran" begitu quotation pertama dibuat
    # -- LeadStage.quotation sudah ada dari awal, cuma belum pernah dipicu
    # otomatis sebelum Fase 20.
    lead.stage = LeadStage.quotation
    db.commit()
    db.refresh(quotation)
    return quotation


def list_quotations(
    db: Session, lead_id: str | None = None, status: QuotationStatus | None = None
) -> list[Quotation]:
    stmt = select(Quotation).order_by(Quotation.created_at.desc())
    if lead_id is not None:
        stmt = stmt.where(Quotation.lead_id == parse_uuid(lead_id))
    if status is not None:
        stmt = stmt.where(Quotation.status == status)
    return list(db.execute(stmt).scalars())


def get_quotation(db: Session, quotation_id: str) -> Quotation:
    return _get_quotation(db, quotation_id)


def submit_quotation_approval(db: Session, quotation_id: str) -> Quotation:
    quotation = _get_quotation(db, quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise HTTPException(
            status_code=409, detail="Hanya quotation berstatus draft yang bisa diajukan approval"
        )
    quotation.status = QuotationStatus.pending_approval
    db.commit()
    db.refresh(quotation)
    audit.log_event(
        db,
        action="quotation.submitted_for_approval",
        entity_type="quotation",
        entity_id=quotation.id,
    )
    return quotation


def decide_quotation(
    db: Session, *, user, quotation_id: str, approved: bool, note: str | None = None
) -> Quotation:
    """Approval single-level: admin/management mana pun boleh memutus --
    pola "tanpa rantai configured" yang sama dengan
    `finance.service.decide_payment_request` (PR tanpa chain). Kalau nanti
    dibutuhkan rantai multi-level per tenant, tinggal contek pola
    `PRApprovalStep`/`PaymentRequestApproval` di modul finance."""
    quotation = _get_quotation(db, quotation_id)
    if quotation.status != QuotationStatus.pending_approval:
        raise HTTPException(
            status_code=409, detail="Quotation ini sudah diputus atau belum diajukan"
        )
    if not approved and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Catatan wajib saat menolak quotation")

    role_val = getattr(user.role, "value", user.role)
    if role_val not in ("admin", "management"):
        raise HTTPException(
            status_code=403, detail="Hanya management yang dapat memutuskan quotation"
        )

    if approved:
        quotation.status = QuotationStatus.approved
        quotation.approved_by = user.id
        quotation.approved_at = datetime.now(UTC)
    else:
        quotation.status = QuotationStatus.rejected
        quotation.rejection_note = note
    db.commit()
    db.refresh(quotation)
    audit.log_event(
        db,
        action="quotation.approved" if approved else "quotation.rejected",
        entity_type="quotation",
        entity_id=quotation.id,
        detail={"note": note} if note else None,
    )
    return quotation


def send_quotation(db: Session, quotation_id: str) -> Quotation:
    from app.modules.presales.rendering import render_document_pdf, store_generated_document

    quotation = _get_quotation(db, quotation_id)
    if quotation.status != QuotationStatus.approved:
        raise HTTPException(
            status_code=409, detail="Quotation harus berstatus approved sebelum dikirim"
        )

    template = quotation.template
    lead = quotation.lead
    schema = json.loads(template.field_schema)
    values = json.loads(quotation.field_values)
    sections = [(f["label"], str(values.get(f["key"], "-"))) for f in schema]

    pdf_bytes = render_document_pdf(
        title="Penawaran Harga",
        subtitle=lead.company_name,
        sections=sections,
        footer_text=template.footer_text,
        accent_color=template.accent_color,
    )
    object_key = store_generated_document(
        object_prefix="quotations", file_name=f"quotation-{quotation.id}.pdf", data=pdf_bytes
    )
    quotation.object_key = object_key
    quotation.status = QuotationStatus.sent
    quotation.sent_at = datetime.now(UTC)
    db.commit()
    db.refresh(quotation)
    audit.log_event(
        db,
        action="quotation.sent",
        entity_type="quotation",
        entity_id=quotation.id,
        object_key=object_key,
    )
    return quotation


def quotation_download_url(db: Session, quotation_id: str) -> str:
    from app.core.storage import presigned_get_url

    quotation = _get_quotation(db, quotation_id)
    if not quotation.object_key:
        raise HTTPException(status_code=404, detail="Quotation ini belum digenerate/dikirim")
    audit.log_event(
        db,
        action="quotation.download_url",
        entity_type="quotation",
        entity_id=quotation.id,
        object_key=quotation.object_key,
    )
    return presigned_get_url(quotation.object_key)


def send_quotation_email(
    db: Session, *, user, quotation_id: str, to_email: str | None = None
) -> dict:
    """Kirim salinan PDF quotation yang sudah digenerate ke email klien.

    Beda dari `send_raw_email_with_attachment` yang no-op senyap bila SMTP
    belum dikonfigurasi (dipakai di alur best-effort seperti invite .ics
    interview) -- di sini aksi dipicu langsung oleh klik staf yang
    mengharapkan hasil pasti, jadi `email_enabled` dicek dulu dan gagal
    lempar 422 kalau belum aktif, supaya tidak ada toast sukses palsu."""
    from app.core.config import get_settings
    from app.core.storage import get_object
    from app.modules.notifications.service import send_raw_email_with_attachment

    quotation = _get_quotation(db, quotation_id)
    if not quotation.object_key:
        raise HTTPException(status_code=404, detail="Quotation ini belum digenerate/dikirim")
    lead = quotation.lead
    recipient = (to_email or "").strip() or lead.contact_email
    if not recipient:
        raise HTTPException(
            status_code=422,
            detail="Email penerima tidak diketahui -- isi email kontak lead atau masukkan manual",
        )
    if not get_settings().email_enabled:
        raise HTTPException(
            status_code=422,
            detail=(
                "SMTP belum dikonfigurasi -- hubungi admin platform untuk "
                "mengaktifkan pengiriman email"
            ),
        )
    pdf_bytes = get_object(quotation.object_key)
    send_raw_email_with_attachment(
        recipient,
        f"Penawaran Harga -- {lead.company_name}",
        f"Terlampir dokumen penawaran harga untuk {lead.company_name}.",
        attachment_bytes=pdf_bytes,
        attachment_filename=f"quotation-{quotation.id}.pdf",
        attachment_maintype="application",
        attachment_subtype="pdf",
    )
    audit.log_event(
        db,
        action="quotation.emailed",
        entity_type="quotation",
        entity_id=quotation.id,
        detail={"to": recipient, "by": getattr(user, "email", "?")},
    )
    return {"sent_to": recipient}


# ---------------- Agreement template (Fase 20 item 3) ----------------


def _get_agreement_template(db: Session, template_id: str) -> AgreementTemplate:
    tmpl = db.get(AgreementTemplate, parse_uuid(template_id))
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template agreement tidak ditemukan")
    return tmpl


def create_agreement_template(db: Session, payload: AgreementTemplateCreate) -> AgreementTemplate:
    tmpl = AgreementTemplate(
        id=uuid4(),
        name=payload.name,
        field_schema=json.dumps([f.model_dump() for f in payload.field_schema]),
        footer_text=payload.footer_text,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def list_agreement_templates(db: Session, active_only: bool = False) -> list[AgreementTemplate]:
    stmt = select(AgreementTemplate).order_by(AgreementTemplate.created_at.desc())
    if active_only:
        stmt = stmt.where(AgreementTemplate.is_active.is_(True))
    return list(db.execute(stmt).scalars())


def get_agreement_template(db: Session, template_id: str) -> AgreementTemplate:
    return _get_agreement_template(db, template_id)


def update_agreement_template(
    db: Session, template_id: str, payload: AgreementTemplateUpdate
) -> AgreementTemplate:
    tmpl = _get_agreement_template(db, template_id)
    data = payload.model_dump(exclude_unset=True)
    if "field_schema" in data:
        data["field_schema"] = json.dumps(data["field_schema"])
    for field, value in data.items():
        setattr(tmpl, field, value)
    db.commit()
    db.refresh(tmpl)
    return tmpl


# ---------------- Agreement (Fase 20 item 3-4) ----------------


def _get_agreement(db: Session, agreement_id: str) -> Agreement:
    agreement = db.get(Agreement, parse_uuid(agreement_id))
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement tidak ditemukan")
    return agreement


def create_agreement(db: Session, *, user, payload: AgreementCreate) -> Agreement:
    lead = _get(db, str(payload.lead_id))
    template = _get_agreement_template(db, str(payload.template_id))

    agreement = Agreement(
        id=uuid4(),
        lead_id=lead.id,
        template_id=template.id,
        field_values=json.dumps(payload.field_values),
        status=AgreementStatus.draft,
        created_by=user.id,
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


def list_agreements(
    db: Session, lead_id: str | None = None, status: AgreementStatus | None = None
) -> list[Agreement]:
    stmt = select(Agreement).order_by(Agreement.created_at.desc())
    if lead_id is not None:
        stmt = stmt.where(Agreement.lead_id == parse_uuid(lead_id))
    if status is not None:
        stmt = stmt.where(Agreement.status == status)
    return list(db.execute(stmt).scalars())


def get_agreement(db: Session, agreement_id: str) -> Agreement:
    return _get_agreement(db, agreement_id)


def submit_agreement_review(db: Session, agreement_id: str) -> Agreement:
    agreement = _get_agreement(db, agreement_id)
    if agreement.status != AgreementStatus.draft:
        raise HTTPException(
            status_code=409, detail="Hanya agreement berstatus draft yang bisa diajukan review"
        )
    agreement.status = AgreementStatus.internal_review
    db.commit()
    db.refresh(agreement)
    audit.log_event(
        db, action="agreement.submitted_for_review", entity_type="agreement", entity_id=agreement.id
    )
    return agreement


def decide_agreement(
    db: Session, *, user, agreement_id: str, approved: bool, note: str | None = None
) -> Agreement:
    """Review internal (klausul legal) single-level -- pola identik
    `decide_quotation`, cuma nama status beda (`internal_review` bukan
    `pending_approval`)."""
    agreement = _get_agreement(db, agreement_id)
    if agreement.status != AgreementStatus.internal_review:
        raise HTTPException(
            status_code=409, detail="Agreement ini sudah diputus atau belum diajukan review"
        )
    if not approved and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Catatan wajib saat menolak agreement")

    role_val = getattr(user.role, "value", user.role)
    if role_val not in ("admin", "management"):
        raise HTTPException(
            status_code=403, detail="Hanya management yang dapat memutuskan agreement"
        )

    if approved:
        agreement.status = AgreementStatus.approved
        agreement.reviewed_by = user.id
        agreement.reviewed_at = datetime.now(UTC)
    else:
        agreement.status = AgreementStatus.declined
        agreement.review_note = note
    db.commit()
    db.refresh(agreement)
    audit.log_event(
        db,
        action="agreement.approved" if approved else "agreement.declined",
        entity_type="agreement",
        entity_id=agreement.id,
        detail={"note": note} if note else None,
    )
    return agreement


def send_agreement_for_signature(
    db: Session, agreement_id: str, *, signer_name: str, signer_email: str
) -> Agreement:
    """Render `.docx`, simpan, lalu kirim ke penyedia TTE lewat
    `esign.service.send_agreement` -- pola sama `recruitment.service.
    send_offering_letter` yang render dulu baru panggil modul esign dengan
    bytes yang sudah jadi (bukan esign yang baca dari storage sendiri)."""
    from app.modules.esign.service import send_agreement as esign_send_agreement
    from app.modules.presales.rendering import render_document_docx, store_generated_document

    agreement = _get_agreement(db, agreement_id)
    if agreement.status != AgreementStatus.approved:
        raise HTTPException(
            status_code=409, detail="Agreement harus berstatus approved sebelum dikirim"
        )

    template = agreement.template
    lead = agreement.lead
    schema = json.loads(template.field_schema)
    values = json.loads(agreement.field_values)
    sections: list[tuple[str, str | list[str]]] = [
        (str(f["label"]), str(values.get(f["key"], "-"))) for f in schema
    ]

    docx_bytes = render_document_docx(
        title="Perjanjian Kerja Sama",
        subtitle=lead.company_name,
        sections=sections,
        footer_text=template.footer_text,
    )
    file_name = f"agreement-{agreement.id}.docx"
    object_key = store_generated_document(
        object_prefix="agreements",
        file_name=file_name,
        data=docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    agreement.object_key = object_key
    agreement.status = AgreementStatus.sent
    agreement.sent_at = datetime.now(UTC)
    db.commit()
    db.refresh(agreement)

    esign_send_agreement(
        db,
        agreement.id,
        docx_bytes=docx_bytes,
        file_name=file_name,
        title="Perjanjian Kerja Sama",
        signer_name=signer_name,
        signer_email=signer_email,
    )
    audit.log_event(
        db,
        action="agreement.sent",
        entity_type="agreement",
        entity_id=agreement.id,
        object_key=object_key,
    )
    db.refresh(agreement)
    return agreement


def agreement_download_url(db: Session, agreement_id: str) -> str:
    from app.core.storage import presigned_get_url

    agreement = _get_agreement(db, agreement_id)
    if not agreement.object_key:
        raise HTTPException(status_code=404, detail="Agreement ini belum digenerate/dikirim")
    audit.log_event(
        db,
        action="agreement.download_url",
        entity_type="agreement",
        entity_id=agreement.id,
        object_key=agreement.object_key,
    )
    return presigned_get_url(agreement.object_key)


def send_agreement_email(
    db: Session, *, user, agreement_id: str, to_email: str | None = None
) -> dict:
    """Kirim salinan .docx agreement yang sudah digenerate ke email klien.

    Terpisah dari `send_agreement_for_signature` (yang mengundang klien
    e-sign lewat provider TTE) -- ini cuma kanal tambahan untuk membagikan
    salinan dokumen, sama pola/alasan dengan `send_quotation_email`."""
    from app.core.config import get_settings
    from app.core.storage import get_object
    from app.modules.notifications.service import send_raw_email_with_attachment

    agreement = _get_agreement(db, agreement_id)
    if not agreement.object_key:
        raise HTTPException(status_code=404, detail="Agreement ini belum digenerate/dikirim")
    lead = agreement.lead
    recipient = (to_email or "").strip() or lead.contact_email
    if not recipient:
        raise HTTPException(
            status_code=422,
            detail="Email penerima tidak diketahui -- isi email kontak lead atau masukkan manual",
        )
    if not get_settings().email_enabled:
        raise HTTPException(
            status_code=422,
            detail=(
                "SMTP belum dikonfigurasi -- hubungi admin platform untuk "
                "mengaktifkan pengiriman email"
            ),
        )
    docx_bytes = get_object(agreement.object_key)
    send_raw_email_with_attachment(
        recipient,
        f"Perjanjian Kerja Sama -- {lead.company_name}",
        f"Terlampir dokumen perjanjian kerja sama untuk {lead.company_name}.",
        attachment_bytes=docx_bytes,
        attachment_filename=f"agreement-{agreement.id}.docx",
        attachment_maintype="application",
        attachment_subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    audit.log_event(
        db,
        action="agreement.emailed",
        entity_type="agreement",
        entity_id=agreement.id,
        detail={"to": recipient, "by": getattr(user, "email", "?")},
    )
    return {"sent_to": recipient}


# ---------------- Lead ----------------


def _resolve_fx_rate(currency: str, fx_rate: float | None) -> float:
    """Fase 46 -- IDR selalu kurs 1 (paksa, abaikan input klien kalau ada
    supaya tidak bisa dipalsukan); currency asing wajib kurs eksplisit
    > 0 dari staf -- tidak ada default diam-diam yang bisa salah kaprah
    menyamakan 1 USD = 1 IDR."""
    if currency == "IDR":
        return 1.0
    if fx_rate is None or fx_rate <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"fx_rate_to_idr wajib diisi (> 0) untuk currency {currency}",
        )
    return fx_rate


def create_lead(db: Session, payload: LeadCreate) -> Lead:
    if payload.company_id is not None:
        company = _get_company(db, str(payload.company_id))
    else:
        if not payload.company_name:
            raise HTTPException(
                status_code=422, detail="company_name wajib diisi jika company_id tidak diberikan"
            )
        company = Company(id=uuid4(), name=payload.company_name, industry=payload.industry)
        db.add(company)
        if payload.contact_name or payload.contact_email or payload.contact_phone:
            db.add(
                Contact(
                    id=uuid4(),
                    company_id=company.id,
                    name=payload.contact_name or payload.company_name,
                    email=payload.contact_email,
                    phone=payload.contact_phone,
                    is_primary=True,
                )
            )

    now = datetime.now(UTC)
    fx_rate = _resolve_fx_rate(payload.currency, payload.fx_rate_to_idr)
    lead = Lead(
        id=uuid4(),
        company_id=company.id,
        estimated_headcount=payload.estimated_headcount,
        estimated_value=payload.estimated_value,
        currency=payload.currency,
        fx_rate_to_idr=fx_rate,
        stage=payload.stage,
        notes=payload.notes,
        stage_changed_at=now,
        last_activity_at=now,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


LEAD_IMPORT_HEADER = [
    "company_name",
    "industry",
    "size",
    "contact_name",
    "department",
    "email",
    "phone",
    "estimated_headcount",
    "estimated_value",
    "notes",
]


def leads_import_template_csv() -> str:
    """Fase 20 item 5 (revisi) -- alternatif aman dari scraping LinkedIn:
    impor massal lead dari CSV (mis. hasil ekspor pameran dagang, direktori
    bisnis publik, atau daftar prospek yang sudah dikumpulkan manual/legal)."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(LEAD_IMPORT_HEADER)
    writer.writerow(
        [
            "PT Contoh Sejahtera",
            "Manufaktur",
            "50-100",
            "Budi Setiawan",
            "HR",
            "budi@contohsejahtera.co.id",
            "081234567890",
            80,
            150_000_000,
            "Tertarik outsourcing security",
        ]
    )
    return buffer.getvalue()


async def import_leads_csv(db: Session, file: UploadFile) -> LeadImportResultOut:
    """Impor CSV lead massal; baris gagal dilaporkan tanpa menghentikan
    lainnya (pola sama seperti `attendance.service.import_csv`). Company
    dicocokkan case-insensitive by nama -- kalau belum ada, dibuat baru
    dengan `source="csv_import"` supaya asal lead tetap terlacak (beda dari
    lead yang diketik manual satu-satu lewat form, `source="manual"`)."""
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    sample = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    result = LeadImportResultOut(companies_created=0, leads_created=0, failed=[])
    companies_cache: dict[str, Company] = {}

    for idx, row in enumerate(reader, start=2):  # baris 1 = header
        company_name = (row.get("company_name") or "").strip()
        try:
            if not company_name:
                raise ValueError("company_name kosong")

            cache_key = company_name.lower()
            company = companies_cache.get(cache_key)
            company_is_new = False
            if company is None:
                company = db.execute(
                    select(Company).where(func.lower(Company.name) == cache_key)
                ).scalar_one_or_none()
            if company is None:
                company = Company(
                    id=uuid4(),
                    name=company_name,
                    industry=(row.get("industry") or "").strip() or None,
                    size=(row.get("size") or "").strip() or None,
                    source="csv_import",
                )
                db.add(company)
                result.companies_created += 1
                company_is_new = True
            companies_cache[cache_key] = company

            contact_name = (row.get("contact_name") or "").strip()
            email = (row.get("email") or "").strip() or None
            phone = (row.get("phone") or "").strip() or None
            if contact_name or email or phone:
                db.add(
                    Contact(
                        id=uuid4(),
                        company_id=company.id,
                        name=contact_name or company_name,
                        department=(row.get("department") or "").strip() or None,
                        email=email,
                        phone=phone,
                        is_primary=company_is_new,
                    )
                )

            headcount_raw = (row.get("estimated_headcount") or "").strip()
            value_raw = (row.get("estimated_value") or "").strip()
            import_now = datetime.now(UTC)
            lead = Lead(
                id=uuid4(),
                company_id=company.id,
                estimated_headcount=int(headcount_raw) if headcount_raw else None,
                estimated_value=float(value_raw) if value_raw else None,
                notes=(row.get("notes") or "").strip() or None,
                stage_changed_at=import_now,
                last_activity_at=import_now,
            )
            db.add(lead)
            result.leads_created += 1
        except (ValueError, TypeError) as exc:
            result.failed.append(
                LeadImportRowFailure(row=idx, company_name=company_name or "-", error=str(exc))
            )

    db.commit()
    if result.failed:
        logger.warning("Impor lead: %d baris gagal", len(result.failed))
    audit.log_event(
        db,
        action="lead.imported",
        entity_type="lead",
        detail={
            "companies_created": result.companies_created,
            "leads_created": result.leads_created,
            "failed_rows": len(result.failed),
        },
    )
    return result


def list_leads(
    db: Session,
    stage: LeadStage | None = None,
    q: str | None = None,
    owner_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c). `owner_id` (Fase 44) -- filter "lead saya" / per staf,
    dipakai juga oleh saved views."""
    stmt = (
        select(Lead).join(Company, Lead.company_id == Company.id).order_by(Lead.created_at.desc())
    )
    if stage is not None:
        stmt = stmt.where(Lead.stage == stage)
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    if owner_id:
        stmt = stmt.where(Lead.owner_id == parse_uuid(owner_id))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_lead(db: Session, lead_id: str) -> Lead:
    return _get(db, lead_id)


def update_lead(db: Session, lead_id: str, payload: LeadUpdate) -> Lead:
    lead = _get(db, lead_id)
    data = payload.model_dump(exclude_unset=True)
    now = datetime.now(UTC)
    # Fase 42 -- `stage_changed_at`/`last_activity_at` auto-diisi di sini,
    # bukan lewat field yang dikirim klien, supaya tidak bisa dipalsukan.
    if "stage" in data and data["stage"] != lead.stage:
        lead.stage_changed_at = now
        lead.last_activity_at = now
    # Fase 46 -- ganti ke currency asing WAJIB sertakan fx_rate_to_idr di
    # request yang sama -- tidak boleh diam-diam pakai kurs lama/stale
    # (mis. bekas 1.0 dari IDR) yang jadi salah kaprah menyamakan nilainya.
    if "currency" in data:
        fx_rate_provided = data.get("fx_rate_to_idr")
        if data["currency"] != "IDR" and fx_rate_provided is None:
            raise HTTPException(
                status_code=422,
                detail=f"fx_rate_to_idr wajib diisi (> 0) untuk currency {data['currency']}",
            )
        data["fx_rate_to_idr"] = _resolve_fx_rate(data["currency"], fx_rate_provided)
    elif "fx_rate_to_idr" in data:
        data["fx_rate_to_idr"] = _resolve_fx_rate(lead.currency, data["fx_rate_to_idr"])
    for field, value in data.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: str) -> None:
    lead = _get(db, lead_id)
    db.delete(lead)
    db.commit()


def add_activity(
    db: Session,
    lead_id: str,
    activity_type: ActivityType,
    content: str,
    due_at: datetime | None = None,
) -> LeadActivity:
    lead = _get(db, lead_id)
    activity = LeadActivity(
        lead_id=lead.id, activity_type=activity_type, content=content, due_at=due_at
    )
    lead.last_activity_at = datetime.now(UTC)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _get_lead_activity(db: Session, activity_id: str) -> LeadActivity:
    activity = db.get(LeadActivity, parse_uuid(activity_id))
    if activity is None:
        raise HTTPException(status_code=404, detail="Aktivitas tidak ditemukan")
    return activity


def set_activity_completed(db: Session, activity_id: str, completed: bool) -> LeadActivity:
    activity = _get_lead_activity(db, activity_id)
    activity.completed_at = datetime.now(UTC) if completed else None
    db.commit()
    db.refresh(activity)
    return activity


def list_due_tasks(
    db: Session, overdue_only: bool = False, include_completed: bool = False
) -> list[dict]:
    """Fase 43 -- daftar 'tugas jatuh tempo' lintas lead (bukan per-lead)
    untuk dashboard follow-up: semua `LeadActivity` yang punya `due_at`,
    join ke Lead+Company biar frontend tidak perlu fetch terpisah."""
    stmt = (
        select(LeadActivity)
        .join(Lead, LeadActivity.lead_id == Lead.id)
        .where(LeadActivity.due_at.is_not(None))
        .order_by(LeadActivity.due_at)
    )
    if not include_completed:
        stmt = stmt.where(LeadActivity.completed_at.is_(None))
    if overdue_only:
        stmt = stmt.where(LeadActivity.due_at < datetime.now(UTC))
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": a.id,
            "lead_id": a.lead_id,
            "company_name": a.lead.company_name,
            "activity_type": a.activity_type,
            "content": a.content,
            "due_at": a.due_at,
            "completed_at": a.completed_at,
            "owner_name": a.lead.owner_name,
        }
        for a in rows
    ]


def _get_lead_contact(db: Session, lead_contact_id: str) -> LeadContact:
    lc = db.get(LeadContact, parse_uuid(lead_contact_id))
    if lc is None:
        raise HTTPException(status_code=404, detail="Kontak lead tidak ditemukan")
    return lc


def add_lead_contact(db: Session, lead_id: str, payload: LeadContactCreate) -> LeadContact:
    """Fase 40 -- tautkan kontak company ke lead ini dengan peran spesifik
    (mis. Decision Maker, Champion). Kontak harus milik company yang sama
    dengan lead -- tidak masuk akal menautkan PIC perusahaan lain."""
    lead = _get(db, lead_id)
    contact = _get_contact(db, str(payload.contact_id))
    if contact.company_id != lead.company_id:
        raise HTTPException(
            status_code=422, detail="Kontak harus berasal dari perusahaan yang sama dengan lead ini"
        )
    existing = db.execute(
        select(LeadContact).where(
            LeadContact.lead_id == lead.id, LeadContact.contact_id == contact.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Kontak ini sudah ditautkan ke lead")

    lc = LeadContact(id=uuid4(), lead_id=lead.id, contact_id=contact.id, role=payload.role)
    db.add(lc)
    db.commit()
    db.refresh(lc)
    return lc


def list_lead_contacts(db: Session, lead_id: str) -> list[LeadContact]:
    lead = _get(db, lead_id)
    return list(lead.lead_contacts)


def update_lead_contact(
    db: Session, lead_contact_id: str, payload: LeadContactUpdate
) -> LeadContact:
    lc = _get_lead_contact(db, lead_contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lc, field, value)
    db.commit()
    db.refresh(lc)
    return lc


def remove_lead_contact(db: Session, lead_contact_id: str) -> None:
    lc = _get_lead_contact(db, lead_contact_id)
    db.delete(lc)
    db.commit()


# ---------------- Saved lead views (Fase 44) ----------------


def create_saved_view(db: Session, *, user, payload: SavedLeadViewCreate) -> SavedLeadView:
    view = SavedLeadView(
        id=uuid4(),
        name=payload.name,
        filters=json.dumps(payload.filters),
        is_shared=payload.is_shared,
        created_by=user.id,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


def list_saved_views(db: Session, *, user) -> list[SavedLeadView]:
    """Punya sendiri (privat/dibagikan) + semua yang dibagikan staf lain --
    beda dari most-list-endpoints yang tidak mem-filter per user, di sini
    sengaja karena view privat orang lain memang bukan urusan staf ini."""
    stmt = (
        select(SavedLeadView)
        .where(or_(SavedLeadView.is_shared.is_(True), SavedLeadView.created_by == user.id))
        .order_by(SavedLeadView.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


def delete_saved_view(db: Session, *, user, view_id: str) -> None:
    view = db.get(SavedLeadView, parse_uuid(view_id))
    if view is None:
        raise HTTPException(status_code=404, detail="Tampilan tersimpan tidak ditemukan")
    if view.created_by != user.id:
        raise HTTPException(
            status_code=403, detail="Hanya pembuat yang bisa menghapus tampilan ini"
        )
    db.delete(view)
    db.commit()


# ---------------- Suppressed contacts (Fase 45) ----------------


def create_suppressed_contact(
    db: Session, *, user, payload: SuppressedContactCreate
) -> SuppressedContact:
    if bool(payload.company_id) == bool(payload.contact_id):
        raise HTTPException(
            status_code=422,
            detail="Isi salah satu: company_id ATAU contact_id (tidak boleh keduanya atau kosong)",
        )
    if payload.company_id is not None:
        _get_company(db, str(payload.company_id))
    if payload.contact_id is not None:
        _get_contact(db, str(payload.contact_id))

    existing = db.execute(
        select(SuppressedContact).where(
            SuppressedContact.company_id == payload.company_id,
            SuppressedContact.contact_id == payload.contact_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Sudah ada di suppression list")

    entry = SuppressedContact(
        id=uuid4(),
        company_id=payload.company_id,
        contact_id=payload.contact_id,
        reason=payload.reason,
        created_by=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_suppressed_contacts(db: Session) -> list[SuppressedContact]:
    stmt = select(SuppressedContact).order_by(SuppressedContact.created_at.desc())
    return list(db.execute(stmt).scalars())


def delete_suppressed_contact(db: Session, entry_id: str) -> None:
    entry = db.get(SuppressedContact, parse_uuid(entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Entri suppression tidak ditemukan")
    db.delete(entry)
    db.commit()


def funnel_stats(db: Session) -> FunnelStats:
    # Fase 46 -- jumlah dalam IDR (estimated_value * fx_rate_to_idr), BUKAN
    # `estimated_value` mentah -- lead currency asing kalau dijumlah apa
    # adanya akan mencampur satuan uang berbeda jadi satu angka yang salah.
    rows = db.execute(
        select(
            Lead.stage,
            func.count(Lead.id),
            func.coalesce(func.sum(Lead.estimated_value * Lead.fx_rate_to_idr), 0.0),
        ).group_by(Lead.stage)
    ).all()
    counts = {s: int(c) for s, c, _ in rows}
    values = {s: float(v or 0.0) for s, _, v in rows}
    stages = [
        FunnelStage(stage=s, count=counts.get(s, 0), total_estimated_value=values.get(s, 0.0))
        for s in LeadStage
    ]
    return FunnelStats(
        stages=stages,
        total_leads=sum(counts.values()),
        won_leads=counts.get(LeadStage.won, 0),
        lost_leads=counts.get(LeadStage.lost, 0),
    )


# ---------------- Custom fields (Fase 41) ----------------


def _get_field_definition(db: Session, field_id: str) -> CustomFieldDefinition:
    fd = db.get(CustomFieldDefinition, parse_uuid(field_id))
    if fd is None:
        raise HTTPException(status_code=404, detail="Field kustom tidak ditemukan")
    return fd


def _validate_entity_exists(db: Session, entity: FieldEntity, entity_id: str) -> None:
    if entity == FieldEntity.lead:
        _get(db, entity_id)
    elif entity == FieldEntity.company:
        _get_company(db, entity_id)
    elif entity == FieldEntity.contact:
        _get_contact(db, entity_id)


def create_custom_field_definition(
    db: Session, payload: CustomFieldDefinitionCreate
) -> CustomFieldDefinition:
    if payload.field_type == FieldType.select and not payload.options:
        raise HTTPException(
            status_code=422, detail="Field bertipe pilihan wajib punya minimal satu opsi"
        )
    existing = db.execute(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.entity == payload.entity, CustomFieldDefinition.key == payload.key
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Key field ini sudah dipakai untuk entitas yang sama"
        )

    fd = CustomFieldDefinition(
        id=uuid4(),
        entity=payload.entity,
        key=payload.key,
        label=payload.label,
        field_type=payload.field_type,
        is_required=payload.is_required,
        position=payload.position,
    )
    fd.options = [
        CustomFieldOption(id=uuid4(), label=opt.label, position=i)
        for i, opt in enumerate(payload.options)
    ]
    db.add(fd)
    db.commit()
    db.refresh(fd)
    return fd


def list_custom_field_definitions(db: Session, entity: FieldEntity) -> list[CustomFieldDefinition]:
    stmt = (
        select(CustomFieldDefinition)
        .where(CustomFieldDefinition.entity == entity)
        .order_by(CustomFieldDefinition.position, CustomFieldDefinition.created_at)
    )
    return list(db.execute(stmt).scalars())


def update_custom_field_definition(
    db: Session, field_id: str, payload: CustomFieldDefinitionUpdate
) -> CustomFieldDefinition:
    fd = _get_field_definition(db, field_id)
    data = payload.model_dump(exclude_unset=True, exclude={"options"})
    for field, value in data.items():
        setattr(fd, field, value)
    if payload.options is not None:
        if fd.field_type == FieldType.select and not payload.options:
            raise HTTPException(
                status_code=422, detail="Field bertipe pilihan wajib punya minimal satu opsi"
            )
        fd.options.clear()
        fd.options = [
            CustomFieldOption(id=uuid4(), label=opt.label, position=i)
            for i, opt in enumerate(payload.options)
        ]
    db.commit()
    db.refresh(fd)
    return fd


def delete_custom_field_definition(db: Session, field_id: str) -> None:
    fd = _get_field_definition(db, field_id)
    db.delete(fd)
    db.commit()


def _validate_field_value(fd: CustomFieldDefinition, value: str | None) -> None:
    if value is None or value == "":
        if fd.is_required:
            raise HTTPException(status_code=422, detail=f"Field '{fd.label}' wajib diisi")
        return
    if fd.field_type == FieldType.number:
        try:
            float(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Field '{fd.label}' harus berupa angka"
            ) from exc
    elif fd.field_type == FieldType.checkbox:
        if value not in ("true", "false"):
            raise HTTPException(status_code=422, detail=f"Field '{fd.label}' harus true/false")
    elif fd.field_type == FieldType.select:
        valid_ids = {str(opt.id) for opt in fd.options}
        if value not in valid_ids:
            raise HTTPException(
                status_code=422, detail=f"Pilihan tidak valid untuk field '{fd.label}'"
            )


def list_custom_field_values(db: Session, entity: FieldEntity, entity_id: str) -> list[dict]:
    """Gabungkan semua definisi field untuk `entity` dengan nilai yang ada
    untuk record `entity_id` -- field yang belum diisi tetap muncul dengan
    value=None supaya frontend bisa render form lengkap sekali fetch."""
    _validate_entity_exists(db, entity, entity_id)
    definitions = list_custom_field_definitions(db, entity)
    values_by_field = {
        v.field_definition_id: v.value
        for v in db.execute(
            select(CustomFieldValue).where(
                CustomFieldValue.entity_id == parse_uuid(entity_id),
                CustomFieldValue.field_definition_id.in_([d.id for d in definitions]),
            )
        ).scalars()
    }
    return [
        {
            "field_definition_id": d.id,
            "key": d.key,
            "label": d.label,
            "field_type": d.field_type,
            "value": values_by_field.get(d.id),
        }
        for d in definitions
    ]


def set_custom_field_value(db: Session, payload: CustomFieldValueIn) -> CustomFieldValue:
    fd = _get_field_definition(db, str(payload.field_definition_id))
    if fd.entity != payload.entity:
        raise HTTPException(status_code=422, detail="Field ini tidak berlaku untuk entitas ini")
    _validate_entity_exists(db, payload.entity, str(payload.entity_id))
    _validate_field_value(fd, payload.value)

    existing = db.execute(
        select(CustomFieldValue).where(
            CustomFieldValue.field_definition_id == fd.id,
            CustomFieldValue.entity_id == payload.entity_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = CustomFieldValue(
            id=uuid4(),
            field_definition_id=fd.id,
            entity_id=payload.entity_id,
            value=payload.value,
        )
        db.add(existing)
    else:
        existing.value = payload.value
    db.commit()
    db.refresh(existing)
    return existing


def convert_lead_to_client(db: Session, lead_id: str):
    """Mengubah lead menjadi klien (dipakai saat lead mencapai tahap deal).

    Data PIC dan nama perusahaan disalin ke master klien; lead ditandai `deal`
    dan terhubung ke klien hasil konversi. Konversi ganda ditolak.
    """
    from app.modules.clients.models import Client

    lead = _get(db, lead_id)
    existing = db.execute(select(Client).where(Client.lead_id == lead.id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Lead ini sudah dikonversi menjadi klien")

    client = Client(
        name=lead.company_name,
        pic_name=lead.contact_name,
        pic_phone=lead.contact_phone,
        pic_email=lead.contact_email,
        lead_id=lead.id,
    )
    lead.stage = LeadStage.won
    db.add(client)
    db.commit()
    db.refresh(client)
    return client
