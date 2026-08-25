from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules.clients.models import Client
from app.modules.finance.models import (
    CashFlowDirection,
    CashFlowEntry,
    Invoice,
    InvoiceStatus,
)
from app.modules.finance.schemas import (
    AgingRow,
    CashFlowCreate,
    InvoiceGenerateRequest,
    InvoiceUpdate,
)
from app.modules.finance.tax_config import (
    DEFAULT_DUE_DAYS,
    DEFAULT_PPH23_RATE,
    DEFAULT_PPN_RATE,
)
from app.modules.hrd.models import Employee
from app.modules.payroll.models import PayrollRun, Payslip
from app.modules.rates.service import get_effective_billing
from app.modules.recruitment.models import JobOrder, Placement


def _get_invoice(db: Session, invoice_id: str) -> Invoice:
    invoice = db.get(Invoice, parse_uuid(invoice_id))
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan")
    return invoice


def _generate_invoice_no(db: Session) -> str:
    count = db.scalar(select(func.count(Invoice.id))) or 0
    return f"INV/{date.today().year}/{count + 1:04d}"


def _payroll_total_for_client(
    db: Session, client_id: UUID, year: int, month: int
) -> float:
    """Total slip gaji karyawan klien (via placement → job order)."""
    run = db.execute(
        select(PayrollRun).where(PayrollRun.year == year, PayrollRun.month == month)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=422,
            detail=f"Belum ada payrol periode {month}/{year} untuk ditagihkan",
        )
    total = db.execute(
        select(func.coalesce(func.sum(Payslip.gross), 0))
        .join(Employee, Payslip.employee_id == Employee.id)
        .join(Placement, Employee.placement_id == Placement.id)
        .join(JobOrder, Placement.job_order_id == JobOrder.id)
        .where(Payslip.run_id == run.id, JobOrder.client_id == client_id)
    ).scalar()
    return float(total or 0)


def generate_invoice(db: Session, payload: InvoiceGenerateRequest) -> Invoice:
    if db.get(Client, payload.client_id) is None:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    duplicate = db.execute(
        select(Invoice).where(
            Invoice.client_id == payload.client_id,
            Invoice.year == payload.year,
            Invoice.month == payload.month,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Invoice untuk periode ini sudah ada")

    payroll_total = _payroll_total_for_client(
        db, payload.client_id, payload.year, payload.month
    )
    # Ambil tarif ber-versi untuk periode invoice (fallback ke konstanta kode)
    billing_cfg = get_effective_billing(db, date(payload.year, payload.month, 1))
    default_ppn = float(billing_cfg.ppn_rate) if billing_cfg else DEFAULT_PPN_RATE
    default_pph23 = float(billing_cfg.pph23_rate) if billing_cfg else DEFAULT_PPH23_RATE
    default_due = int(billing_cfg.due_days) if billing_cfg else DEFAULT_DUE_DAYS

    ppn_rate = payload.ppn_rate if payload.ppn_rate is not None else default_ppn
    pph23_rate = payload.pph23_rate if payload.pph23_rate is not None else default_pph23

    subtotal = payroll_total + payload.fee_amount
    ppn_amount = round(subtotal * ppn_rate)
    pph23_amount = round(payload.fee_amount * pph23_rate)
    total_due = subtotal + ppn_amount - pph23_amount

    invoice = Invoice(
        client_id=payload.client_id,
        invoice_no=_generate_invoice_no(db),
        year=payload.year,
        month=payload.month,
        payroll_total=payroll_total,
        fee_amount=payload.fee_amount,
        ppn_rate=ppn_rate,
        ppn_amount=ppn_amount,
        pph23_rate=pph23_rate,
        pph23_amount=pph23_amount,
        total_due=total_due,
        status=InvoiceStatus.draft,
        issued_date=date.today(),
        due_date=date.today() + timedelta(days=default_due),
        notes=payload.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def list_invoices(
    db: Session, status: InvoiceStatus | None = None, client_id: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    if client_id:
        stmt = stmt.where(Invoice.client_id == parse_uuid(client_id))
    return list(db.execute(stmt).scalars())


def get_invoice(db: Session, invoice_id: str) -> Invoice:
    return _get_invoice(db, invoice_id)


def update_invoice(db: Session, invoice_id: str, payload: InvoiceUpdate) -> Invoice:
    invoice = _get_invoice(db, invoice_id)
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for field, value in data.items():
        setattr(invoice, field, value)
    if new_status is not None and new_status != invoice.status:
        if invoice.status == InvoiceStatus.paid and new_status != InvoiceStatus.paid:
            raise HTTPException(
                status_code=409, detail="Invoice yang sudah dibayar tidak bisa diubah"
            )
        invoice.status = new_status
        if new_status == InvoiceStatus.paid:
            invoice.paid_at = datetime.now(UTC)
    db.commit()
    db.refresh(invoice)
    return invoice


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    return ">60"


def aging_report(db: Session) -> list[AgingRow]:
    """Invoice belum dibayar yang melewati jatuh tempo, dikelompokkan per bucket."""
    stmt = (
        select(Invoice)
        .where(Invoice.status.in_([InvoiceStatus.draft, InvoiceStatus.sent]))
        .where(Invoice.due_date.is_not(None))
        .where(Invoice.due_date < date.today())
        .order_by(Invoice.due_date)
    )
    today = date.today()
    rows: list[AgingRow] = []
    for invoice in db.execute(stmt).scalars():
        if invoice.due_date is None:
            continue
        days_overdue = (today - invoice.due_date).days
        rows.append(
            AgingRow(
                invoice_id=invoice.id,
                invoice_no=invoice.invoice_no,
                client_name=invoice.client.name,
                total_due=float(invoice.total_due),
                due_date=invoice.due_date,
                days_overdue=days_overdue,
                bucket=_aging_bucket(days_overdue),
            )
        )
    return rows


# ---------- Cash flow ----------


def create_cashflow_entry(db: Session, payload: CashFlowCreate) -> CashFlowEntry:
    entry = CashFlowEntry(**payload.model_dump())
    if entry.entry_date is None:
        entry.entry_date = date.today()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_cashflow(
    db: Session, year: int | None = None, month: int | None = None
) -> list[CashFlowEntry]:
    stmt = select(CashFlowEntry).order_by(CashFlowEntry.entry_date.desc())
    if year is not None:
        stmt = stmt.where(func.extract("year", CashFlowEntry.entry_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", CashFlowEntry.entry_date) == month)
    return list(db.execute(stmt).scalars())


def cashflow_summary(
    db: Session, year: int, month: int | None = None
) -> dict:
    stmt = select(
        CashFlowEntry.direction, func.coalesce(func.sum(CashFlowEntry.amount), 0)
    ).where(func.extract("year", CashFlowEntry.entry_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", CashFlowEntry.entry_date) == month)
    stmt = stmt.group_by(CashFlowEntry.direction)
    inflow = 0.0
    outflow = 0.0
    for direction, amount_total in db.execute(stmt).all():
        if direction == CashFlowDirection.inflow:
            inflow = float(amount_total)
        else:
            outflow = float(amount_total)
    return {
        "year": year,
        "month": month,
        "inflow": inflow,
        "outflow": outflow,
        "net": inflow - outflow,
    }
