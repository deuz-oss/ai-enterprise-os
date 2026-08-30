from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import FINANCE_ROLES, PAYMENT_REQUEST_ROLES
from app.core.security import (
    get_current_user,
    require_any_licensed_app,
    require_roles,
)
from app.modules.finance import service
from app.modules.finance.models import InvoiceStatus, PaymentRequestStatus
from app.modules.finance.schemas import (
    AgingRow,
    CashFlowCreate,
    CashFlowOut,
    CashFlowSummary,
    InvoiceGenerateRequest,
    InvoiceOut,
    InvoiceUpdate,
    TaxInvoiceReplace,
    TaxInvoiceSet,
)

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*FINANCE_ROLES))],
)


# ---------- Payment Request (lintas jalur; eksekusi oleh Finance) ----------

pr_router = APIRouter(
    prefix="/payment-requests",
    tags=["payment-request"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_any_licensed_app("hr_payroll", "operations_billing")),
        Depends(require_roles(*PAYMENT_REQUEST_ROLES)),
    ],
)


@pr_router.get("")
def list_payment_requests(
    status_filter: PaymentRequestStatus | None = Query(None, alias="status"),
    pr_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.list_payment_requests_detail(db, status=status_filter, pr_type=pr_type)


@pr_router.get("/approval-chain")
def get_approval_chain(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Rantai approval PR tenant (urut tahap)."""
    return service.get_approval_chain(db, user.tenant_id)


@pr_router.put("/approval-chain")
def set_approval_chain(
    payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Ganti rantai approval PR tenant (admin/management).

    Payload: `{"steps": [{"approver_role": "management"}, {"approver_id": "..."}]}`.
    """
    raw = payload.get("steps") if isinstance(payload, dict) else None
    if raw is not None and not isinstance(raw, list):
        raise HTTPException(status_code=422, detail="steps harus berupa daftar")
    chain = service.set_approval_chain(db, user=user, steps=raw or [])
    return {"steps": chain}


@pr_router.post("", status_code=201)
def create_payment_request(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Ops (proyek) / HR (internal) mengajukan PR dari payroll run final."""

    desc = payload.get("description")
    pr = service.create_payment_request(
        db,
        user=user,
        pr_type=str(payload.get("pr_type") or "internal"),
        amount=float(payload.get("amount") or 0),
        payroll_run_id=payload.get("payroll_run_id") or None,
        description=desc if isinstance(desc, str) else None,
    )
    return {"id": str(pr.id), "pr_number": pr.pr_number, "status": pr.status.value}


@pr_router.post("/{pr_id}/approve")
def approve_pr(pr_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pr = service.decide_payment_request(db, user=user, pr_id=str(pr_id), approved=True)
    return {"id": str(pr.id), "status": pr.status.value}


@pr_router.post("/{pr_id}/reject")
def reject_pr(
    pr_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    pr = service.decide_payment_request(
        db, user=user, pr_id=str(pr_id), approved=False, note=(payload or {}).get("note")
    )
    return {"id": str(pr.id), "status": pr.status.value}


@pr_router.post("/{pr_id}/execute")
def execute_pr(pr_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pr = service.execute_payment_request(db, user=user, pr_id=str(pr_id))
    return {"id": str(pr.id), "status": pr.status.value, "executed_at": pr.executed_at}


# ---------- Invoice ----------


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.list_invoices(db, status=status_filter, client_id=client_id)


@router.post("/invoices/generate", response_model=InvoiceOut, status_code=201)
def generate_invoice(payload: InvoiceGenerateRequest, db: Session = Depends(get_db)):
    """Buat invoice otomatis dari total payrol klien + fee + PPN - PPh23."""
    return service.generate_invoice(db, payload)


@router.get("/invoices/aging", response_model=list[AgingRow])
def aging_report(db: Session = Depends(get_db)):
    return service.aging_report(db)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    return service.get_invoice(db, invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: str, payload: InvoiceUpdate, db: Session = Depends(get_db)):
    return service.update_invoice(db, invoice_id, payload)


# ---------- Faktur Pajak DJP — PRD v3.0 Revenue Cloud ----------


@router.put("/invoices/{invoice_id}/tax-invoice", response_model=InvoiceOut)
def set_tax_invoice(invoice_id: str, payload: TaxInvoiceSet, db: Session = Depends(get_db)):
    return service.set_tax_invoice(db, invoice_id, payload)


@router.post("/invoices/{invoice_id}/tax-invoice/send", response_model=InvoiceOut)
def send_tax_invoice(invoice_id: str, db: Session = Depends(get_db)):
    return service.send_tax_invoice(db, invoice_id)


@router.post("/invoices/{invoice_id}/tax-invoice/cancel", response_model=InvoiceOut)
def cancel_tax_invoice(invoice_id: str, db: Session = Depends(get_db)):
    return service.cancel_tax_invoice(db, invoice_id)


@router.post("/invoices/{invoice_id}/tax-invoice/replace", response_model=InvoiceOut)
def replace_tax_invoice(invoice_id: str, payload: TaxInvoiceReplace, db: Session = Depends(get_db)):
    pengganti_ref = str(payload.pengganti_ref) if payload.pengganti_ref else None
    return service.replace_tax_invoice(db, invoice_id, pengganti_ref)


@router.get("/invoices/{invoice_id}/tax-invoice/pdf")
def tax_invoice_pdf(invoice_id: str, db: Session = Depends(get_db)):
    pdf_bytes, filename = service.tax_invoice_pdf(db, invoice_id)
    from fastapi import Response

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Cash flow ----------


@router.get("/cashflow", response_model=list[CashFlowOut])
def list_cashflow(
    year: int | None = Query(None), month: int | None = Query(None), db: Session = Depends(get_db)
):
    return service.list_cashflow(db, year=year, month=month)


@router.get("/cashflow/summary", response_model=CashFlowSummary)
def cashflow_summary(
    year: int = Query(...), month: int | None = Query(None), db: Session = Depends(get_db)
):
    return service.cashflow_summary(db, year=year, month=month)


@router.post("/cashflow", response_model=CashFlowOut, status_code=status.HTTP_201_CREATED)
def create_cashflow(payload: CashFlowCreate, db: Session = Depends(get_db)):
    return service.create_cashflow_entry(db, payload)
