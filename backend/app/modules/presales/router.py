from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import PRESALES_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.clients.schemas import ClientOut
from app.modules.presales import service
from app.modules.presales.models import AgreementStatus, LeadStage, QuotationStatus
from app.modules.presales.schemas import (
    ActivityCreate,
    ActivityOut,
    AgreementCreate,
    AgreementDeclineIn,
    AgreementOut,
    AgreementSendIn,
    AgreementTemplateCreate,
    AgreementTemplateOut,
    AgreementTemplateUpdate,
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    ContactCreate,
    ContactOut,
    ContactUpdate,
    FunnelStats,
    LeadCreate,
    LeadOut,
    LeadUpdate,
    QuotationCreate,
    QuotationOut,
    QuotationRejectIn,
    QuotationTemplateCreate,
    QuotationTemplateOut,
    QuotationTemplateUpdate,
)

router = APIRouter(
    prefix="/leads",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)

# Router terpisah (bukan sub-path /leads/companies) karena Company/Contact
# adalah entitas sendiri, dipakai lintas Lead (Fase 20 item 1) -- lihat
# main.py untuk pendaftaran + guard lisensi sales_crm yang sama.
companies_router = APIRouter(
    prefix="/companies",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@companies_router.get("", response_model=list[CompanyOut])
def list_companies(
    response: Response,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_companies(db, q=q, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return rows


@companies_router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    return service.create_company(db, payload)


@companies_router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, db: Session = Depends(get_db)):
    return service.get_company(db, company_id)


@companies_router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: str, payload: CompanyUpdate, db: Session = Depends(get_db)):
    return service.update_company(db, company_id, payload)


@companies_router.post(
    "/{company_id}/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED
)
def add_contact(company_id: str, payload: ContactCreate, db: Session = Depends(get_db)):
    return service.add_contact(db, company_id, payload)


@companies_router.get("/{company_id}/contacts", response_model=list[ContactOut])
def list_contacts(company_id: str, db: Session = Depends(get_db)):
    return service.list_contacts(db, company_id)


@companies_router.patch("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: str, payload: ContactUpdate, db: Session = Depends(get_db)):
    return service.update_contact(db, contact_id, payload)


@companies_router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: str, db: Session = Depends(get_db)):
    service.delete_contact(db, contact_id)


# Fase 20 item 2 — template visual Quotation (infrastruktur bersama, lihat
# `presales/rendering.py`). Router terpisah, prefix sendiri, sama seperti
# companies_router di atas.
quotation_templates_router = APIRouter(
    prefix="/quotation-templates",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@quotation_templates_router.get("", response_model=list[QuotationTemplateOut])
def list_quotation_templates(active_only: bool = False, db: Session = Depends(get_db)):
    return service.list_quotation_templates(db, active_only=active_only)


@quotation_templates_router.post(
    "", response_model=QuotationTemplateOut, status_code=status.HTTP_201_CREATED
)
def create_quotation_template(payload: QuotationTemplateCreate, db: Session = Depends(get_db)):
    return service.create_quotation_template(db, payload)


@quotation_templates_router.get("/{template_id}", response_model=QuotationTemplateOut)
def get_quotation_template(template_id: str, db: Session = Depends(get_db)):
    return service.get_quotation_template(db, template_id)


@quotation_templates_router.patch("/{template_id}", response_model=QuotationTemplateOut)
def update_quotation_template(
    template_id: str, payload: QuotationTemplateUpdate, db: Session = Depends(get_db)
):
    return service.update_quotation_template(db, template_id, payload)


# Fase 20 item 2 — Quotation (draft -> pending_approval -> approved/rejected
# -> sent). Router terpisah lagi, prefix sendiri.
quotations_router = APIRouter(
    prefix="/quotations",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@quotations_router.get("", response_model=list[QuotationOut])
def list_quotations(
    lead_id: str | None = None,
    status: QuotationStatus | None = None,
    db: Session = Depends(get_db),
):
    return service.list_quotations(db, lead_id=lead_id, status=status)


@quotations_router.post("", response_model=QuotationOut, status_code=status.HTTP_201_CREATED)
def create_quotation(
    payload: QuotationCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.create_quotation(db, user=user, payload=payload)


@quotations_router.get("/{quotation_id}", response_model=QuotationOut)
def get_quotation(quotation_id: str, db: Session = Depends(get_db)):
    return service.get_quotation(db, quotation_id)


@quotations_router.post("/{quotation_id}/submit-approval", response_model=QuotationOut)
def submit_quotation_approval(quotation_id: str, db: Session = Depends(get_db)):
    return service.submit_quotation_approval(db, quotation_id)


@quotations_router.post("/{quotation_id}/approve", response_model=QuotationOut)
def approve_quotation(
    quotation_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.decide_quotation(db, user=user, quotation_id=quotation_id, approved=True)


@quotations_router.post("/{quotation_id}/reject", response_model=QuotationOut)
def reject_quotation(
    quotation_id: str,
    payload: QuotationRejectIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.decide_quotation(
        db, user=user, quotation_id=quotation_id, approved=False, note=payload.note
    )


@quotations_router.post("/{quotation_id}/send", response_model=QuotationOut)
def send_quotation(quotation_id: str, db: Session = Depends(get_db)):
    return service.send_quotation(db, quotation_id)


@quotations_router.get("/{quotation_id}/download-url")
def quotation_download_url(quotation_id: str, db: Session = Depends(get_db)):
    return {"url": service.quotation_download_url(db, quotation_id)}


# Fase 20 item 3 — template visual Agreement.
agreement_templates_router = APIRouter(
    prefix="/agreement-templates",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@agreement_templates_router.get("", response_model=list[AgreementTemplateOut])
def list_agreement_templates(active_only: bool = False, db: Session = Depends(get_db)):
    return service.list_agreement_templates(db, active_only=active_only)


@agreement_templates_router.post(
    "", response_model=AgreementTemplateOut, status_code=status.HTTP_201_CREATED
)
def create_agreement_template(payload: AgreementTemplateCreate, db: Session = Depends(get_db)):
    return service.create_agreement_template(db, payload)


@agreement_templates_router.get("/{template_id}", response_model=AgreementTemplateOut)
def get_agreement_template(template_id: str, db: Session = Depends(get_db)):
    return service.get_agreement_template(db, template_id)


@agreement_templates_router.patch("/{template_id}", response_model=AgreementTemplateOut)
def update_agreement_template(
    template_id: str, payload: AgreementTemplateUpdate, db: Session = Depends(get_db)
):
    return service.update_agreement_template(db, template_id, payload)


# Fase 20 item 3-4 — Agreement (draft -> internal_review -> approved/declined
# -> sent -> signed/declined lewat esign).
agreements_router = APIRouter(
    prefix="/agreements",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@agreements_router.get("", response_model=list[AgreementOut])
def list_agreements(
    lead_id: str | None = None,
    status: AgreementStatus | None = None,
    db: Session = Depends(get_db),
):
    return service.list_agreements(db, lead_id=lead_id, status=status)


@agreements_router.post("", response_model=AgreementOut, status_code=status.HTTP_201_CREATED)
def create_agreement(
    payload: AgreementCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.create_agreement(db, user=user, payload=payload)


@agreements_router.get("/{agreement_id}", response_model=AgreementOut)
def get_agreement(agreement_id: str, db: Session = Depends(get_db)):
    return service.get_agreement(db, agreement_id)


@agreements_router.post("/{agreement_id}/submit-review", response_model=AgreementOut)
def submit_agreement_review(agreement_id: str, db: Session = Depends(get_db)):
    return service.submit_agreement_review(db, agreement_id)


@agreements_router.post("/{agreement_id}/approve", response_model=AgreementOut)
def approve_agreement(
    agreement_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.decide_agreement(db, user=user, agreement_id=agreement_id, approved=True)


@agreements_router.post("/{agreement_id}/decline", response_model=AgreementOut)
def decline_agreement(
    agreement_id: str,
    payload: AgreementDeclineIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.decide_agreement(
        db, user=user, agreement_id=agreement_id, approved=False, note=payload.note
    )


@agreements_router.post("/{agreement_id}/send-esign", response_model=AgreementOut)
def send_agreement_for_signature(
    agreement_id: str, payload: AgreementSendIn, db: Session = Depends(get_db)
):
    return service.send_agreement_for_signature(
        db, agreement_id, signer_name=payload.signer_name, signer_email=payload.signer_email
    )


@agreements_router.get("/{agreement_id}/download-url")
def agreement_download_url(agreement_id: str, db: Session = Depends(get_db)):
    return {"url": service.agreement_download_url(db, agreement_id)}


@router.get("", response_model=list[LeadOut])
def list_leads(
    response: Response,
    stage: LeadStage | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_leads(db, stage=stage, q=q, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/funnel", response_model=FunnelStats)
def funnel(db: Session = Depends(get_db)):
    return service.funnel_stats(db)


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    return service.create_lead(db, payload)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    return service.get_lead(db, lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: str, payload: LeadUpdate, db: Session = Depends(get_db)):
    return service.update_lead(db, lead_id, payload)


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    service.delete_lead(db, lead_id)


@router.post("/{lead_id}/convert", response_model=ClientOut, status_code=201)
def convert_lead(lead_id: str, db: Session = Depends(get_db)):
    """Konversi lead menjadi klien (untuk lead yang sudah deal)."""
    return service.convert_lead_to_client(db, lead_id)


@router.post("/{lead_id}/activities", response_model=ActivityOut, status_code=201)
def add_activity(lead_id: str, payload: ActivityCreate, db: Session = Depends(get_db)):
    return service.add_activity(db, lead_id, payload.activity_type, payload.content)


@router.get("/{lead_id}/activities", response_model=list[ActivityOut])
def list_activities(lead_id: str, db: Session = Depends(get_db)):
    lead = service.get_lead(db, lead_id)
    return list(lead.activities)
