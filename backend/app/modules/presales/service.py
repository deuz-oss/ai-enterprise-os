import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
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
    Lead,
    LeadActivity,
    LeadStage,
    Quotation,
    QuotationStatus,
    QuotationTemplate,
)
from app.modules.presales.schemas import (
    AgreementCreate,
    AgreementTemplateCreate,
    AgreementTemplateUpdate,
    CompanyCreate,
    CompanyUpdate,
    ContactCreate,
    ContactUpdate,
    FunnelStage,
    FunnelStats,
    LeadCreate,
    LeadUpdate,
    QuotationCreate,
    QuotationTemplateCreate,
    QuotationTemplateUpdate,
)


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
    company = Company(id=uuid4(), name=payload.name, industry=payload.industry, size=payload.size)
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
    sections = [(f["label"], str(values.get(f["key"], "-"))) for f in schema]

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


# ---------------- Lead ----------------


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

    lead = Lead(
        id=uuid4(),
        company_id=company.id,
        estimated_headcount=payload.estimated_headcount,
        estimated_value=payload.estimated_value,
        stage=payload.stage,
        notes=payload.notes,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_leads(
    db: Session,
    stage: LeadStage | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c)."""
    stmt = (
        select(Lead).join(Company, Lead.company_id == Company.id).order_by(Lead.created_at.desc())
    )
    if stage is not None:
        stmt = stmt.where(Lead.stage == stage)
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_lead(db: Session, lead_id: str) -> Lead:
    return _get(db, lead_id)


def update_lead(db: Session, lead_id: str, payload: LeadUpdate) -> Lead:
    lead = _get(db, lead_id)
    data = payload.model_dump(exclude_unset=True)
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
    db: Session, lead_id: str, activity_type: ActivityType, content: str
) -> LeadActivity:
    lead = _get(db, lead_id)
    activity = LeadActivity(lead_id=lead.id, activity_type=activity_type, content=content)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def funnel_stats(db: Session) -> FunnelStats:
    rows = db.execute(
        select(
            Lead.stage,
            func.count(Lead.id),
            func.coalesce(func.sum(Lead.estimated_value), 0.0),
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
