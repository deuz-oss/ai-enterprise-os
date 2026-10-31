"""Auto-reload saldo kredit sungguhan (Fase 28 lanjutan, rencana §6).

Pemicu: setiap debit (`record_credit_transaction`) memanggil `maybe_enqueue`
-- bila sisa (jatah siklus + saldo top-up) di bawah ambang, satu baris
`payment_charges(purpose=auto_reload)` dibuat (outbox, transaksi yang sama
dengan debit) dan kunci `auto_reload_in_flight_charge_id` dipasang lewat
compare-and-set -> paling banyak satu charge berjalan per tenant. Nominal
tetap Rp100.000, tanpa batas bulanan (PRD §4.4.1).

Eksekusi: (1) cron `POST /platform/internal/run-auto-reload` (proaktif +
rekonsiliasi), (2) jalur reaktif sinkron di `service.assert_metered_allowed`.

Gagal: backoff +15 menit / +1 jam / +6 jam lalu berhenti (K6); kode gagal
permanen tidak dicoba ulang. Bila saldo sudah habis, fitur metered diblokir
(`metered_blocked_at`) sampai ada kredit masuk (auto-reload/top-up sukses).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.tenancy import get_tenant, set_tenant
from app.modules.billing.models import (
    AUTO_RELOAD_AMOUNT_IDR,
    ChargePurpose,
    ChargeStatus,
    CreditTransactionType,
    PaymentCharge,
    TenantBudgetCycle,
    TenantCreditAccount,
    TenantPaymentMethod,
)
from app.modules.billing.service import (
    _get_or_create_credit_account,
    as_aware,
    audit_add,
    default_payment_method,
    notify_billing_users,
    now_utc,
    record_credit_transaction,
    total_remaining,
)

logger = logging.getLogger(__name__)

BACKOFF = [timedelta(minutes=15), timedelta(hours=1), timedelta(hours=6)]
MAX_FAILURES = len(BACKOFF) + 1  # percobaan awal + 3 retry, lalu berhenti
# TODO verifikasi Xendit: daftar kode gagal permanen yang persis.
PERMANENT_FAILURE_CODES = {
    "EXPIRED_CARD",
    "INVALID_PAYMENT_METHOD",
    "PAYMENT_METHOD_NOT_ACTIVE",
    "ACCOUNT_NOT_FOUND",
    "REQUIRES_ACTION",
}


def _eligible_method(
    db: Session, account: TenantCreditAccount, *, ignore_backoff: bool = False
) -> TenantPaymentMethod | None:
    if not account.auto_reload_enabled or account.auto_reload_threshold is None:
        return None
    if account.auto_reload_in_flight_charge_id is not None:
        return None
    if account.auto_reload_failure_count >= MAX_FAILURES:
        return None
    next_at = as_aware(account.auto_reload_next_attempt_at)
    if not ignore_backoff and next_at is not None and next_at > now_utc():
        return None
    return default_payment_method(db, account)


def _enqueue(
    db: Session, tenant_id: UUID, account: TenantCreditAccount, pm: TenantPaymentMethod
) -> PaymentCharge | None:
    charge_id = uuid4()
    result = db.execute(
        update(TenantCreditAccount)
        .where(
            TenantCreditAccount.id == account.id,
            TenantCreditAccount.auto_reload_in_flight_charge_id.is_(None),
        )
        .values(auto_reload_in_flight_charge_id=charge_id)
        .execution_options(synchronize_session="evaluate")
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        return None  # request lain sudah memegang kunci
    charge = PaymentCharge(
        id=charge_id,
        tenant_id=tenant_id,
        purpose=ChargePurpose.auto_reload,
        payment_method_id=pm.id,
        amount=AUTO_RELOAD_AMOUNT_IDR,
        idempotency_key=f"aeos-ar-{tenant_id}-{charge_id.hex}",
        status=ChargeStatus.pending,
        attempt_no=account.auto_reload_failure_count + 1,
    )
    db.add(charge)
    audit_add(
        db,
        action="billing.auto_reload_triggered",
        entity_type="payment_charge",
        entity_id=charge_id,
        detail={"amount": str(AUTO_RELOAD_AMOUNT_IDR), "attempt_no": charge.attempt_no},
        tenant_id=tenant_id,
    )
    db.flush()
    return charge


def maybe_enqueue(
    db: Session,
    tenant_id: UUID,
    account: TenantCreditAccount,
    cycle: TenantBudgetCycle | None,
) -> PaymentCharge | None:
    """Dipanggil setelah debit di-flush. Tanpa commit (outbox)."""
    pm = _eligible_method(db, account)
    if pm is None:
        return None
    remaining = (cycle.remaining if cycle else 0.0) + float(account.balance)
    if Decimal(str(remaining)) >= Decimal(str(account.auto_reload_threshold)):
        return None
    return _enqueue(db, tenant_id, account, pm)


def try_reactive_reload(db: Session, tenant_id: UUID) -> bool:
    """Satu percobaan auto-reload sinkron (saldo kurang di awal aksi metered).
    Hanya dipanggil bila sesi tidak punya tulisan tertunda. True bila sukses."""
    from app.modules.billing import charges

    account = _get_or_create_credit_account(db, tenant_id)
    pm = _eligible_method(db, account)
    if pm is None:
        return False
    charge = _enqueue(db, tenant_id, account, pm)
    if charge is None:
        return False
    charge_id = charge.id
    db.commit()
    result = charges.execute_charge(db, charge_id)
    return result.status == ChargeStatus.succeeded


def on_charge_success(db: Session, charge: PaymentCharge) -> None:
    """Efek sukses (dipanggil `charges.apply_charge_success`, tanpa commit)."""
    from app.modules.billing import receipts
    from app.modules.billing.payment_methods import payment_method_label

    pm = db.get(TenantPaymentMethod, charge.payment_method_id)
    amount = Decimal(charge.amount)
    receipt = receipts.issue_receipt(
        db,
        tenant_id=charge.tenant_id,
        lines=[
            {
                "description": "Auto-reload saldo kredit Aeos",
                "qty": 1,
                "unit_price": str(amount),
                "amount": str(amount),
            }
        ],
        total=amount,
        payment_method_label=payment_method_label(pm) if pm else "Metode bayar tersimpan",
        provider_reference=charge.provider_charge_id,
        issued_at=now_utc(),
        charge=charge,
    )
    record_credit_transaction(
        db,
        amount=float(amount),
        ref_event="billing.auto_reload",
        ref_entity_type="payment_charge",
        ref_entity_id=str(charge.id),
        allow_negative=True,
        tx_type=CreditTransactionType.topup_auto_reload,
        receipt_id=receipt.id,
    )
    account = _get_or_create_credit_account(db, charge.tenant_id)
    if account.auto_reload_in_flight_charge_id == charge.id:
        account.auto_reload_in_flight_charge_id = None
    account.auto_reload_failure_count = 0
    account.auto_reload_next_attempt_at = None
    account.auto_reload_last_error = None
    account.metered_blocked_at = None
    account.metered_block_reason = None
    audit_add(
        db,
        action="billing.auto_reload_succeeded",
        entity_type="payment_charge",
        entity_id=charge.id,
        detail={"amount": str(amount), "receipt_number": receipt.receipt_number},
        tenant_id=charge.tenant_id,
    )


def on_charge_failure(db: Session, charge: PaymentCharge, code: str) -> None:
    """Efek gagal (tanpa commit): lepas kunci, backoff, blokir metered bila
    saldo sudah habis, notifikasi. Detail TANPA data kartu."""
    account = _get_or_create_credit_account(db, charge.tenant_id)
    if account.auto_reload_in_flight_charge_id == charge.id:
        account.auto_reload_in_flight_charge_id = None
    permanent = code in PERMANENT_FAILURE_CODES
    count = MAX_FAILURES if permanent else account.auto_reload_failure_count + 1
    account.auto_reload_failure_count = count
    account.auto_reload_last_error = code[:200]
    account.auto_reload_next_attempt_at = (
        now_utc() + BACKOFF[count - 1] if count <= len(BACKOFF) else None
    )
    audit_add(
        db,
        action="billing.auto_reload_failed",
        entity_type="payment_charge",
        entity_id=charge.id,
        detail={"failure_code": code, "attempt_no": charge.attempt_no, "permanent": permanent},
        tenant_id=charge.tenant_id,
    )
    db.flush()
    if total_remaining(db, charge.tenant_id) <= 0 and account.metered_blocked_at is None:
        account.metered_blocked_at = now_utc()
        account.metered_block_reason = "auto_reload_failed"
        audit_add(
            db,
            action="billing.metered_blocked",
            entity_type="tenant_credit_account",
            entity_id=account.id,
            detail={"reason": "auto_reload_failed", "failure_code": code},
            tenant_id=charge.tenant_id,
        )
    notify_billing_users(
        db,
        charge.tenant_id,
        title="Auto-reload saldo gagal",
        body=(
            f"Charge auto-reload Rp100.000 gagal ({code}). "
            + (
                "Percobaan berikutnya dijadwalkan otomatis."
                if account.auto_reload_next_attempt_at
                else "Tidak dicoba ulang otomatis -- perbarui metode bayar atau top up manual."
            )
            + " Bila saldo habis, fitur berbayar diblokir; data tetap bisa diakses."
        ),
    )


def _due_charges(db: Session, tenant_id: UUID) -> list[UUID]:
    now = now_utc()
    rows = db.execute(
        select(PaymentCharge)
        .where(PaymentCharge.tenant_id == tenant_id)
        .where(PaymentCharge.purpose == ChargePurpose.auto_reload)
        .where(
            PaymentCharge.status.in_(
                [ChargeStatus.pending, ChargeStatus.unknown, ChargeStatus.processing]
            )
        )
    ).scalars()
    due = []
    for charge in rows:
        deadline = as_aware(charge.next_retry_at)
        if charge.status == ChargeStatus.pending or deadline is None or deadline <= now:
            due.append(charge.id)
    return due


def run_for_tenant(db: Session, tenant_id: UUID) -> int:
    """Proses charge jatuh tempo + pemicu proaktif satu tenant. Return jumlah
    charge yang dieksekusi."""
    from app.core.security import _is_billing_bypass
    from app.modules.billing import charges

    executed = 0
    for charge_id in _due_charges(db, tenant_id):
        charges.execute_charge(db, charge_id)
        executed += 1
    if _is_billing_bypass(db, tenant_id):
        return executed
    account = _get_or_create_credit_account(db, tenant_id)
    pm = _eligible_method(db, account)
    if pm is not None:
        remaining = total_remaining(db, tenant_id)
        if Decimal(str(remaining)) < Decimal(str(account.auto_reload_threshold)):
            charge = _enqueue(db, tenant_id, account, pm)
            if charge is not None:
                charge_id = charge.id
                db.commit()
                charges.execute_charge(db, charge_id)
                executed += 1
    db.commit()
    return executed


def run_auto_reload_for_all_tenants(db: Session) -> dict:
    """Cron `POST /platform/internal/run-auto-reload`. Iterasi tabel `tenants`
    (tanpa RLS) lalu `set_tenant()` per tenant sebelum menyentuh tabel ber-RLS
    -- pola sama `cycle_close.run_cycle_charge_for_all_tenants`."""
    from app.modules.platform.models import Tenant

    previous = get_tenant()
    tenant_ids = [row[0] for row in db.execute(select(Tenant.id)).all()]
    executed: dict[str, int] = {}
    try:
        for tenant_id in tenant_ids:
            set_tenant(tenant_id)
            try:
                count = run_for_tenant(db, tenant_id)
            except Exception:  # noqa: BLE001 - satu tenant gagal tidak menghentikan cron
                logger.exception("Auto-reload gagal diproses untuk tenant %s", tenant_id)
                db.rollback()
                continue
            if count:
                executed[str(tenant_id)] = count
    finally:
        set_tenant(previous)
    return {"tenants": len(executed), "charges_executed": sum(executed.values())}
