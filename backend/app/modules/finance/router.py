from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.modules.finance import service
from app.modules.finance.models import InvoiceStatus
from app.modules.finance.schemas import (
    AgingRow,
    CashFlowCreate,
    CashFlowOut,
    CashFlowSummary,
    InvoiceGenerateRequest,
    InvoiceOut,
    InvoiceUpdate,
)

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    dependencies=[Depends(get_current_user), Depends(require_roles("finance", "management"))],
)


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
def update_invoice(
    invoice_id: str, payload: InvoiceUpdate, db: Session = Depends(get_db)
):
    return service.update_invoice(db, invoice_id, payload)


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
