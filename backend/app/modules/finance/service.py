from collections.abc import Sequence
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
    PaymentRequestApproval,
    PaymentRequestStatus,
    PRApprovalStep,
)
from app.modules.finance.schemas import (
    AgingRow,
    CashFlowCreate,
    InvoiceGenerateRequest,
    InvoiceUpdate,
    TaxInvoiceSet,
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


# Peran staf yang boleh dipasang sebagai approver rantai (bukan karyawan/platform).
_CHAIN_ROLES = ("admin", "management", "finance", "hr", "operations", "business_dev", "recruiter")


def _chain_steps(db: Session, tenant_id) -> list[PRApprovalStep]:
    return list(
        db.execute(
            select(PRApprovalStep)
            .where(PRApprovalStep.tenant_id == tenant_id)
            .order_by(PRApprovalStep.seq)
        )
        .scalars()
        .all()
    )


def get_approval_chain(db: Session, tenant_id) -> list[dict]:
    """Rantai approval aktif tenant, urut tahap."""
    from app.modules.auth.models import User

    steps = _chain_steps(db, tenant_id)
    user_ids = {s.approver_id for s in steps if s.approver_id}
    names: dict = {}
    if user_ids:
        rows = db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
        names = {uid: name for uid, name in rows}
    return [
        {
            "seq": s.seq,
            "approver_id": str(s.approver_id) if s.approver_id else None,
            "approver_name": names.get(s.approver_id),
            "approver_role": s.approver_role,
        }
        for s in steps
    ]


def set_approval_chain(db: Session, *, user, steps: list[dict]) -> list[dict]:
    """Ganti seluruh rantai approval tenant (admin/management).

    Payload: daftar tahap berurutan; tiap tahap wajib punya tepat satu dari
    `approver_id` (user spesifik) atau `approver_role` (peran staf).
    """
    from app.modules.auth.models import User

    role_val = getattr(user.role, "value", user.role)
    if role_val not in ("admin", "management"):
        raise HTTPException(status_code=403, detail="Hanya admin/management dapat mengatur rantai")

    clean: list[dict] = []
    for i, raw in enumerate(steps or [], start=1):
        approver_id = raw.get("approver_id") or None
        approver_role = (raw.get("approver_role") or "").strip() or None
        if bool(approver_id) == bool(approver_role):
            raise HTTPException(
                status_code=422,
                detail=f"Tahap {i}: isi tepat salah satu dari approver_id atau approver_role",
            )
        if approver_id is not None:
            target = db.get(User, parse_uuid(str(approver_id)))
            if target is None or target.tenant_id != user.tenant_id:
                raise HTTPException(status_code=404, detail=f"Tahap {i}: user tidak ditemukan")
            t_role = getattr(target.role, "value", target.role)
            if t_role == "employee":
                raise HTTPException(
                    status_code=422, detail=f"Tahap {i}: karyawan tidak bisa menjadi approver"
                )
        else:
            if approver_role not in _CHAIN_ROLES:
                raise HTTPException(
                    status_code=422, detail=f"Tahap {i}: peran '{approver_role}' tidak valid"
                )
        clean.append({"seq": i, "approver_id": approver_id, "approver_role": approver_role})

    for old in _chain_steps(db, user.tenant_id):
        db.delete(old)
    for item in clean:
        db.add(
            PRApprovalStep(
                tenant_id=user.tenant_id,
                seq=item["seq"],
                approver_id=parse_uuid(item["approver_id"]) if item["approver_id"] else None,
                approver_role=item["approver_role"],
            )
        )
    db.commit()
    audit.log_event(
        db,
        action="payment_request.chain_updated",
        entity_type="tenant",
        entity_id=user.tenant_id,
        detail={"steps": clean},
    )
    return get_approval_chain(db, user.tenant_id)


def _step_approvers(db: Session, tenant_id, step: PRApprovalStep) -> list:
    """Resolusi penerima notifikasi satu tahap: user spesifik atau semua user berperan tsb."""
    from app.modules.auth.models import User, UserRole

    stmt = select(User).where(User.tenant_id == tenant_id, User.is_active.is_(True))
    if step.approver_id is not None:
        stmt = stmt.where(User.id == step.approver_id)
        return list(db.execute(stmt).scalars())
    role = UserRole(step.approver_role) if step.approver_role in UserRole.__members__ else None
    if role is None:
        return []
    return list(db.execute(stmt.where(User.role == role)).scalars())


def _pr_progress(db: Session, pr: PaymentRequest, steps: list[PRApprovalStep]) -> dict:
    """Ringkasan progres rantai untuk satu PR."""
    decisions = (
        db.execute(
            select(PaymentRequestApproval)
            .where(PaymentRequestApproval.payment_request_id == pr.id)
            .order_by(PaymentRequestApproval.step_no)
        )
        .scalars()
        .all()
    )
    total = len(steps)
    approved_count = sum(1 for d in decisions if d.approved)
    pending_seq = next(
        (s.seq for s in steps if not any(d.step_no == s.seq and d.approved for d in decisions)),
        None,
    )
    return {
        "total_steps": total,
        "current_step": min(approved_count + 1, total) if total else None,
        "pending_step": pending_seq,
        "decisions": [
            {
                "step_no": d.step_no,
                "approver_id": str(d.approver_id),
                "approved": d.approved,
                "note": d.note,
                "decided_at": d.decided_at.isoformat(),
            }
            for d in decisions
        ],
    }


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
    # Notifikasi approver tahap pertama bila rantai dikonfigurasi;
    # tanpa rantai → legacy: semua admin + management tenant.
    from app.modules.auth.models import User, UserRole

    steps = _chain_steps(db, user.tenant_id)
    approvers: Sequence[User]
    if steps:
        approvers = _step_approvers(db, user.tenant_id, steps[0])
    else:
        approvers = (
            db.execute(
                select(User).where(
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
            user_id=uid.id,
            title=f"Payment Request menunggu persetujuan — {pr.pr_number}",
            body=f"{pr.description or pr.pr_type}: Rp{float(pr.amount):,.0f}",
            category="payment",
            entity_type="payment_request",
            entity_id=pr.id,
        )
    # Fase 11: kartu interaktif di channel payroll (best-effort).
    if run_ref is not None:
        try:
            from app.modules.chat.service import ensure_payroll_channel, send_card_message

            ch = ensure_payroll_channel(db, run_ref)
            if ch:
                send_card_message(
                    db,
                    user=user,
                    channel_id=str(ch.id),
                    title=f"PR {pr.pr_number} menunggu persetujuan",
                    body=f"{pr.description or pr.pr_type} — Rp{float(pr.amount):,.0f}",
                    actions=[
                        {"id": f"approve_pr:{pr.id}", "label": "Setujui", "style": "primary"},
                        {"id": f"reject_pr:{pr.id}", "label": "Tolak", "style": "danger"},
                    ],
                    card_type="pr_approval",
                )
        except Exception:
            pass
    return pr


def decide_payment_request(
    db: Session, *, user, pr_id: str, approved: bool, note: str | None = None
) -> PaymentRequest:
    """Putuskan PR pada tahap rantai approval yang sedang berjalan (PRD §7).

    - Rantai terkonfigurasi → hanya approver tahap berjalan (user spesifik atau
      peran yang cocok) yang dapat memutus; setujui tahap non-akhir melanjutkan
      ke tahap berikutnya, tolak langsung membatalkan seluruh PR.
    - Tanpa rantai → legacy: management/admin mana pun.
    """
    from app.modules.notifications.service import notify

    pr = db.get(PaymentRequest, parse_uuid(pr_id))
    if pr is None:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    if pr.status != PaymentRequestStatus.waiting_superior:
        raise HTTPException(status_code=409, detail="PR sudah diputus sebelumnya")
    if not approved and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Catatan wajib saat menolak PR")

    role_val = getattr(user.role, "value", user.role)
    steps = _chain_steps(db, user.tenant_id)
    next_step: PRApprovalStep | None = None

    if not steps:
        # Legacy tanpa rantai: management/admin mana pun.
        if role_val not in ("admin", "management"):
            raise HTTPException(status_code=403, detail="Hanya management yang dapat memutuskan PR")
        step_no = 1
    else:
        decisions = (
            db.execute(
                select(PaymentRequestApproval).where(
                    PaymentRequestApproval.payment_request_id == pr.id,
                    PaymentRequestApproval.approved.is_(True),
                )
            )
            .scalars()
            .all()
        )
        done_seqs = {d.step_no for d in decisions}
        pending = next((s for s in steps if s.seq not in done_seqs), None)
        if pending is None:
            raise HTTPException(status_code=409, detail="Rantai approval sudah selesai")
        allowed = False
        if pending.approver_id is not None:
            allowed = user.id == pending.approver_id
        elif pending.approver_role is not None:
            allowed = role_val == pending.approver_role
        if not allowed:
            label = f"tahap {pending.seq} ({pending.approver_role or 'approver khusus'})"
            raise HTTPException(status_code=403, detail=f"Anda bukan approver {label} untuk PR ini")
        step_no = pending.seq
        next_step = next((s for s in steps if s.seq > pending.seq), None)
    db.add(
        PaymentRequestApproval(
            tenant_id=pr.tenant_id,
            payment_request_id=pr.id,
            step_no=step_no,
            approver_id=user.id,
            approved=approved,
            note=(note or "").strip()[:500] or None,
        )
    )

    final_approver = user.id
    if approved and steps and next_step is not None:
        # Tahap non-akhir: PR tetap menunggu approver berikutnya.
        for nxt in _step_approvers(db, pr.tenant_id, next_step):
            notify(
                db,
                user_id=nxt.id,
                title=f"PR {pr.pr_number} menunggu persetujuan Anda — tahap {next_step.seq}",
                body=f"{pr.description or pr.pr_type}: Rp{float(pr.amount):,.0f}",
                category="payment",
                entity_type="payment_request",
                entity_id=pr.id,
            )
        final_approver = None

    if approved and (not steps or next_step is None):
        pr.status = PaymentRequestStatus.approved
        pr.approver_id = final_approver
        pr.decided_at = datetime.now(UTC)
        pr.decision_note = (note or "").strip()[:500] or None
    elif not approved:
        pr.status = PaymentRequestStatus.rejected
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
        detail={
            "approved": approved,
            "status": pr.status.value,
            "step": step_no,
            "chain": bool(steps),
        },
    )
    notify(
        db,
        user_id=pr.requester_id,
        title=f"PR {pr.pr_number} {'disetujui' if approved else 'ditolak'}"
        + (" sementara (tahap berikutnya)" if approved and steps and next_step is not None else ""),
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
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[PaymentRequest], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c)."""
    stmt = select(PaymentRequest).order_by(PaymentRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(PaymentRequest.status == status)
    if pr_type:
        stmt = stmt.where(PaymentRequest.pr_type == pr_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


# ---------- Faktur Pajak DJP — PRD v3.0 Revenue Cloud ----------


def set_tax_invoice(db: Session, invoice_id: str, payload: TaxInvoiceSet) -> Invoice:
    inv = _get_invoice(db, invoice_id)
    data = payload.model_dump(exclude_unset=True, exclude={"tax_invoice_status"})
    no_seri = data.get("no_seri_faktur")
    if no_seri and no_seri != inv.no_seri_faktur:
        dupe = db.execute(
            select(Invoice.id).where(Invoice.no_seri_faktur == no_seri, Invoice.id != inv.id)
        ).scalar_one_or_none()
        if dupe is not None:
            raise HTTPException(
                status_code=409, detail=f"No. Seri Faktur {no_seri} sudah dipakai invoice lain"
            )
    for field, value in data.items():
        setattr(inv, field, value)
    inv.tax_invoice_status = payload.tax_invoice_status or "draft"
    db.commit()
    db.refresh(inv)
    audit.log_event(
        db,
        action="invoice.tax_invoice_set",
        entity_type="invoice",
        entity_id=str(inv.id),
        detail={"no_seri": inv.no_seri_faktur},
    )
    return inv


def send_tax_invoice(db: Session, invoice_id: str) -> Invoice:
    from app.core.config import get_settings

    inv = _get_invoice(db, invoice_id)
    settings = get_settings()
    # Validasi minimal
    if not inv.no_seri_faktur or not inv.lawan_npwp:
        raise HTTPException(status_code=422, detail="Lawan NPWP dan No Seri Faktur wajib diisi")
    if not settings.efaktur_api_url or settings.efaktur_provider == "":
        # Simulasi
        inv.tax_invoice_status = "approved"
        inv.efaktur_nsr = f"NSFP-SIM-{inv.no_seri_faktur}"
        inv.efaktur_qr_url = f"https://djponline.pajak.go.id/qr/{inv.no_seri_faktur}"
        inv.efaktur_payload = '{"simulasi": true}'
    else:
        # Real DJP call would go here — stub approved
        inv.tax_invoice_status = "terkirim_djp"
        inv.efaktur_payload = '{"stub": "terkirim"}'
    inv.faktur_status_detail = None
    db.commit()
    db.refresh(inv)
    audit.log_event(
        db,
        action="invoice.tax_invoice_sent",
        entity_type="invoice",
        entity_id=str(inv.id),
        detail={"status": inv.tax_invoice_status},
    )
    return inv


def cancel_tax_invoice(db: Session, invoice_id: str) -> Invoice:
    inv = _get_invoice(db, invoice_id)
    inv.tax_invoice_status = "dibatalkan"
    db.commit()
    db.refresh(inv)
    audit.log_event(
        db, action="invoice.tax_invoice_cancelled", entity_type="invoice", entity_id=str(inv.id)
    )
    return inv


def replace_tax_invoice(db: Session, invoice_id: str, pengganti_ref: str | None) -> Invoice:
    inv = _get_invoice(db, invoice_id)
    if pengganti_ref:
        try:
            inv.faktur_pengganti_ref = parse_uuid(pengganti_ref)
        except Exception:
            pass
    inv.tax_invoice_status = "pengganti"
    db.commit()
    db.refresh(inv)
    audit.log_event(
        db,
        action="invoice.tax_invoice_replaced",
        entity_type="invoice",
        entity_id=str(inv.id),
        detail={"pengganti_ref": pengganti_ref},
    )
    return inv


def tax_invoice_pdf(db: Session, invoice_id: str) -> tuple[bytes, str]:
    """Render PDF faktur pajak (reportlab) — draft lokal atau salinan hasil DJP.

    Bukan render resmi e-Faktur DJP (itu dilakukan DJP saat submit sungguhan);
    ini dokumen internal/draft yang mengikuti data faktur tersimpan.
    """
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    inv = _get_invoice(db, invoice_id)
    seller_name = "-"
    try:
        from app.core.tenancy import get_tenant
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, get_tenant()) if get_tenant() else None
        seller_name = tenant.name if tenant else "-"
    except Exception:
        pass

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="Faktur Pajak",
    )
    styles = getSampleStyleSheet()
    accent = colors.HexColor("#0f7b6d")
    h1 = ParagraphStyle("FPTitle", parent=styles["Title"], fontSize=16, textColor=accent)
    label = ParagraphStyle(
        "FPLabel", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#666666")
    )
    body = ParagraphStyle("FPBody", parent=styles["Normal"], fontSize=10, leading=14)

    def esc(value) -> str:
        from xml.sax.saxutils import escape

        return escape(str(value)) if value is not None else "-"

    def rupiah(value) -> str:
        return f"Rp{float(value):,.0f}" if value is not None else "-"

    is_simulasi = (inv.efaktur_nsr or "").startswith("NSFP-SIM-")
    story: list = [
        Paragraph("FAKTUR PAJAK", h1),
        Paragraph(
            "DOKUMEN SIMULASI — belum dikirim ke DJP" if is_simulasi else "e-Faktur DJP",
            label,
        ),
        Spacer(1, 6 * mm),
        Paragraph(f"No. Seri Faktur: <b>{esc(inv.no_seri_faktur)}</b>", body),
        Paragraph(f"Tanggal: {esc(inv.tax_invoice_date)}", body),
        Paragraph(f"Kode Transaksi: {esc(inv.kode_transaksi)}", body),
        Paragraph(f"NSFP: {esc(inv.efaktur_nsr)}", body),
        Spacer(1, 6 * mm),
        Paragraph("Pengusaha Kena Pajak (penjual)", label),
        Paragraph(esc(seller_name), body),
        Spacer(1, 4 * mm),
        Paragraph("Lawan Transaksi (pembeli)", label),
        Paragraph(f"<b>{esc(inv.lawan_nama or inv.client.name)}</b>", body),
        Paragraph(f"NPWP: {esc(inv.lawan_npwp)}", body),
        Paragraph(esc(inv.lawan_alamat), body),
        Spacer(1, 6 * mm),
    ]

    table_data = [
        ["Uraian", "DPP", "PPN"],
        [
            f"Invoice {inv.invoice_no} · {inv.month:02d}/{inv.year}",
            rupiah(inv.dpp_amount),
            rupiah(inv.ppn_amount),
        ],
    ]
    table = Table(table_data, colWidths=[90 * mm, 42 * mm, 42 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    if inv.efaktur_qr_url:
        story.append(Paragraph(f"QR verifikasi: {esc(inv.efaktur_qr_url)}", label))
    if inv.faktur_status_detail:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"Catatan: {esc(inv.faktur_status_detail)}", label))

    doc.build(story)
    return buffer.getvalue(), f"faktur-{inv.no_seri_faktur or inv.invoice_no}.pdf"


def list_payment_requests_detail(
    db: Session,
    status: PaymentRequestStatus | None = None,
    pr_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Daftar PR + progres rantai approval per baris."""
    rows, total = list_payment_requests(
        db, status=status, pr_type=pr_type, limit=limit, offset=offset
    )
    steps_cache: dict = {}
    result: list[dict] = []
    for p in rows:
        if p.tenant_id not in steps_cache:
            steps_cache[p.tenant_id] = _chain_steps(db, p.tenant_id)
        result.append(
            {
                "id": str(p.id),
                "pr_number": p.pr_number,
                "pr_type": p.pr_type,
                "payroll_run_id": str(p.payroll_run_id) if p.payroll_run_id else None,
                "amount": float(p.amount),
                "description": p.description,
                "status": p.status.value,
                "decision_note": p.decision_note,
                "created_at": p.created_at.isoformat(),
                "progress": _pr_progress(db, p, steps_cache[p.tenant_id]),
            }
        )
    return result, total
