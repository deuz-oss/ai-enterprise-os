from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.clients.models import Client
from app.modules.finance.models import (
    CashFlowDirection,
    CashFlowEntry,
    Invoice,
    InvoiceStatus,
    PaymentRequest,
    PaymentRequestStatus,
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
    db: Session, client_id: UUID, year: int, month: int, run_id: UUID | None = None
) -> float:
    """Total slip gaji karyawan klien (via placement → job order).

    Bila run_id diberikan (payrol proyek dua jalur), total dihitung dari
    line-item Saltab: Σ earnings + Σ passthrough (BPJS perusahaan).
    """
    if run_id is not None:
        from app.modules.payroll.models import PayslipComponent

        rows = (
            db.execute(select(Payslip.id).where(Payslip.run_id == parse_uuid(str(run_id))))
            .scalars()
            .all()
        )
        if not rows:
            raise HTTPException(
                status_code=422,
                detail=f"Belum ada slip gaji pada payrol {str(run_id)[:8]} untuk ditagihkan",
            )
        comps = db.execute(
            select(PayslipComponent.ctype, func.coalesce(func.sum(PayslipComponent.amount), 0))
            .where(PayslipComponent.payslip_id.in_(rows))
            .group_by(PayslipComponent.ctype)
        ).all()
        totals = {ctype.value: float(amount) for ctype, amount in comps}
        return totals.get("earnings", 0) + totals.get("passthrough", 0)

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


def generate_invoice(
    db: Session, payload: InvoiceGenerateRequest, run_id: UUID | None = None
) -> Invoice:
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
        db,
        payload.client_id,
        payload.year,
        payload.month,
        run_id=run_id or payload.run_id,
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

    # Fase 10: jurnal otomatis invoice_issued (idempoten, best-effort).
    try:
        from app.modules.accounting.service import post_auto_event

        ppn_out = round(ppn_amount)
        revenue = round(subtotal)
        lines = [
            ("1-1200", float(total_due), 0.0),
            ("4-1000", 0.0, revenue),
        ]
        if ppn_out:
            lines.append(("2-1300", 0.0, ppn_out))
        post = post_auto_event(  # noqa: F841
            db,
            tenant_id=invoice.tenant_id,
            event_code="invoice_issued",
            source_ref_type="invoice",
            source_ref_id=invoice.id,
            entry_date=invoice.issued_date or date.today(),
            description=f"Invoice {invoice.invoice_no} — {payload.notes or ''}".strip(),
            lines=lines,
        )
    except Exception:  # noqa: BLE001 - jurnal tidak boleh memblokir bisnis
        import logging

        logging.getLogger(__name__).exception("Auto-journal invoice_issued gagal")
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
            # Fase 10: jurnal otomatis invoice_paid (idempoten).
            try:
                from app.modules.accounting.service import post_auto_event

                post_auto_event(
                    db,
                    tenant_id=invoice.tenant_id,
                    event_code="invoice_paid",
                    source_ref_type="invoice",
                    source_ref_id=invoice.id,
                    entry_date=date.today(),
                    description=f"Pelunasan invoice {invoice.invoice_no}",
                    lines=[
                        ("1-1100", float(invoice.total_due), 0.0),
                        ("1-1200", 0.0, float(invoice.total_due)),
                    ],
                )
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).exception("Auto-journal invoice_paid gagal")
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


def cashflow_summary(db: Session, year: int, month: int | None = None) -> dict:
    stmt = select(CashFlowEntry.direction, func.coalesce(func.sum(CashFlowEntry.amount), 0)).where(
        func.extract("year", CashFlowEntry.entry_date) == year
    )
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


# ---------- Payment Request (PRD §7) ----------


def _next_pr_number(db: Session) -> str:
    count = db.scalar(select(func.count(PaymentRequest.id))) or 0
    return f"PR/{date.today().year}/{count + 1:04d}"


def create_payment_request(
    db: Session,
    *,
    user,
    pr_type: str,
    amount: float,
    payroll_run_id=None,
    description: str | None = None,
) -> PaymentRequest:
    """Ops (proyek) / HR (internal) mengajukan PR pembayaran gaji."""
    from app.modules.notifications.service import notify

    if pr_type not in ("proyek", "internal"):
        raise HTTPException(status_code=422, detail="Tipe PR harus proyek atau internal")
    run_ref = None
    if payroll_run_id is not None:
        from app.modules.payroll.models import PayrollRun

        run_ref = db.get(PayrollRun, parse_uuid(str(payroll_run_id)))
        if run_ref is None:
            raise HTTPException(status_code=404, detail="Payroll run tidak ditemukan")
        if run_ref.status.value != "final":
            raise HTTPException(
                status_code=422, detail="PR hanya untuk payroll run berstatus final"
            )
        if amount <= 0:
            amount = sum(float(s.net_pay) for s in run_ref.slips)
    pr = PaymentRequest(
        pr_number=_next_pr_number(db),
        pr_type=pr_type,
        payroll_run_id=run_ref.id if run_ref else None,
        amount=round(amount),
        description=(description or "").strip()[:500]
        or (
            f"Pembayaran gaji {run_ref.month}/{run_ref.year} ({run_ref.run_type.value})"
            if run_ref
            else None
        ),
        status=PaymentRequestStatus.waiting_superior,
        requester_id=user.id,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    audit.log_event(
        db,
        action="payment_request.created",
        entity_type="payment_request",
        entity_id=pr.id,
        detail={"number": pr.pr_number, "type": pr.pr_type, "amount": float(pr.amount)},
    )
    # Notifikasi ke approver (admin + management tenant).
    from app.modules.auth.models import User, UserRole

    approvers = (
        db.execute(
            select(User.id).where(
                User.tenant_id == user.tenant_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.management]),
            )
        )
        .scalars()
        .all()
    )
    for uid in approvers:
        notify(
            db,
            user_id=uid,
            title=f"Payment Request menunggu persetujuan — {pr.pr_number}",
            body=f"{pr.description or pr.pr_type}: Rp{float(pr.amount):,.0f}",
            category="payment",
            entity_type="payment_request",
            entity_id=pr.id,
        )
    return pr


def decide_payment_request(
    db: Session, *, user, pr_id: str, approved: bool, note: str | None = None
) -> PaymentRequest:
    """Atasan (management/admin) menyetujui / menolak PR."""
    from app.modules.notifications.service import notify

    pr = db.get(PaymentRequest, parse_uuid(pr_id))
    if pr is None:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    if pr.status != PaymentRequestStatus.waiting_superior:
        raise HTTPException(status_code=409, detail="PR sudah diputus sebelumnya")
    if user.role != "admin" and user.role.value != "management":
        raise HTTPException(status_code=403, detail="Hanya management yang dapat memutuskan PR")
    if not approved and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Catatan wajib saat menolak PR")

    pr.status = PaymentRequestStatus.approved if approved else PaymentRequestStatus.rejected
    pr.approver_id = user.id
    pr.decided_at = datetime.now(UTC)
    pr.decision_note = (note or "").strip()[:500] or None
    db.commit()
    db.refresh(pr)
    audit.log_event(
        db,
        action="payment_request.decided",
        entity_type="payment_request",
        entity_id=pr.id,
        detail={"approved": approved, "status": pr.status.value},
    )
    notify(
        db,
        user_id=pr.requester_id,
        title=f"PR {pr.pr_number} {'disetujui atasan' if approved else 'ditolak'}",
        body=pr.decision_note,
        category="payment",
        entity_type="payment_request",
        entity_id=pr.id,
    )
    return pr


def execute_payment_request(db: Session, *, user, pr_id: str) -> PaymentRequest:
    """Finance menjalankan pembayaran (checklist transfer per bank menyusul)."""
    from app.modules.notifications.service import notify

    pr = db.get(PaymentRequest, parse_uuid(pr_id))
    if pr is None:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    if pr.status != PaymentRequestStatus.approved:
        raise HTTPException(status_code=409, detail="PR belum disetujui atasan")
    if user.role not in ("finance", "management", "admin") and user.role.value not in (
        "finance",
        "management",
        "admin",
    ):
        raise HTTPException(status_code=403, detail="Hanya Finance yang dapat mengeksekusi PR")
    pr.status = PaymentRequestStatus.executed
    pr.executed_at = datetime.now(UTC)
    pr.executed_by_id = user.id
    db.commit()
    db.refresh(pr)
    audit.log_event(
        db,
        action="payment_request.executed",
        entity_type="payment_request",
        entity_id=pr.id,
        detail={"amount": float(pr.amount)},
    )
    notify(
        db,
        user_id=pr.requester_id,
        title=f"PR {pr.pr_number} dieksekusi Finance",
        body=f"Pembayaran Rp{float(pr.amount):,.0f} diproses.",
        category="payment",
        entity_type="payment_request",
        entity_id=pr.id,
    )
    # Fase 10: jurnal otomatis pr_executed (idempoten, best-effort).
    try:
        from app.modules.accounting.service import post_auto_event

        post_auto_event(
            db,
            tenant_id=pr.tenant_id,
            event_code="pr_executed",
            source_ref_type="payment_request",
            source_ref_id=pr.id,
            entry_date=date.today(),
            description=f"Eksekusi PR {pr.pr_number}",
            lines=[
                ("2-1000", round(float(pr.amount)), 0.0),
                ("1-1100", 0.0, round(float(pr.amount))),
            ],
        )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("Auto-journal pr_executed gagal")
    return pr


def list_payment_requests(
    db: Session,
    status: PaymentRequestStatus | None = None,
    pr_type: str | None = None,
) -> list[PaymentRequest]:
    stmt = select(PaymentRequest).order_by(PaymentRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(PaymentRequest.status == status)
    if pr_type:
        stmt = stmt.where(PaymentRequest.pr_type == pr_type)
    return list(db.execute(stmt).scalars())
