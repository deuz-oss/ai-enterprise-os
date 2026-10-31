"""Perpanjangan langganan & aturan gagal bayar (Fase 28 lanjutan, rencana §8).

Renewal dikendalikan cron Aeos (`POST /platform/internal/run-renewals`,
keputusan K10), bukan Xendit Recurring:

- Tanpa metode bayar default (atau penegakan nonaktif): invoice renewal
  diterbitkan H-7 sebelum `current_period_end`.
- Dengan metode bayar default + penegakan aktif: charge merchant-initiated
  pada hari setelah `current_period_end`.
- Gagal (penegakan aktif) -> `menunggak` seketika (grace default 0 hari,
  K4): `require_active_subscription` menolak semua modul bisnis, sementara
  endpoint billing akun tetap terbuka agar tenant bisa membayar. Retry
  otomatis H+1/H+3/H+7 dari tanggal menunggak (K6); batal otomatis setelah
  `BILLING_PAST_DUE_CANCEL_DAYS` (default 30).
- Bayar tunggakan: masa baru dihitung dari jatuh tempo LAMA (K13), harga
  renewal = harga & diskon terkini (K14).

Flag `BILLING_RENEWAL_ENFORCEMENT=false` (default, K18): hanya invoice +
notifikasi, tanpa charge otomatis dan tanpa penguncian akses.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.money import to_decimal
from app.core.tenancy import get_tenant, set_tenant
from app.modules.billing.models import (
    BillingPeriod,
    ChargePurpose,
    ChargeStatus,
    CreditTransaction,
    CreditTransactionType,
    PaymentCharge,
    PaymentIntent,
    PaymentIntentStatus,
    PaymentIntentType,
    SubscriptionStatus,
    TenantBudgetCycle,
    TenantPaymentMethod,
    TenantSubscription,
)
from app.modules.billing.service import (
    _get_open_cycle,
    _get_or_create_credit_account,
    as_aware,
    audit_add,
    current_subscription,
    default_payment_method,
    notify_billing_users,
    now_utc,
    price_for,
    total_remaining,
)

logger = logging.getLogger(__name__)

RETRY_DAYS = [1, 3, 7]
INVOICE_LEAD_DAYS = 7


def renewal_price(sub: TenantSubscription) -> tuple[Decimal, Decimal]:
    """Harga terkini (K14). Bila paket tahunan sudah tidak ditawarkan (env
    diskon dikosongkan), pakai snapshot `period_fee` langganan berjalan."""
    try:
        return price_for(sub.tier, sub.billing_period)
    except HTTPException:
        return to_decimal(sub.period_fee), to_decimal(sub.discount_percent)


def _payer_email(db: Session, tenant_id: UUID) -> str:
    from app.modules.auth.models import User, UserRole
    from app.modules.billing.payment_methods import get_or_create_profile

    profile = get_or_create_profile(db, tenant_id)
    if profile.billing_email:
        return profile.billing_email
    email = db.execute(
        select(User.email).where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.role.in_([UserRole.admin, UserRole.finance, UserRole.management]),
        )
    ).scalar()
    return email or "billing@aeos.local"


def _pending_charge(db: Session, sub: TenantSubscription) -> PaymentCharge | None:
    return (
        db.execute(
            select(PaymentCharge)
            .where(PaymentCharge.subscription_id == sub.id)
            .where(PaymentCharge.purpose == ChargePurpose.renewal)
            .where(
                PaymentCharge.status.in_(
                    [ChargeStatus.pending, ChargeStatus.processing, ChargeStatus.unknown]
                )
            )
        )
        .scalars()
        .first()
    )


def _pending_invoice(db: Session, sub: TenantSubscription) -> PaymentIntent | None:
    return (
        db.execute(
            select(PaymentIntent)
            .where(PaymentIntent.subscription_id == sub.id)
            .where(PaymentIntent.type == PaymentIntentType.renewal)
            .where(PaymentIntent.status == PaymentIntentStatus.pending)
        )
        .scalars()
        .first()
    )


def create_renewal_charge(
    db: Session, sub: TenantSubscription, pm: TenantPaymentMethod, attempt_no: int
) -> PaymentCharge:
    amount, _ = renewal_price(sub)
    period_tag = sub.current_period_end.strftime("%Y%m%d") if sub.current_period_end else "na"
    charge = PaymentCharge(
        id=uuid4(),
        tenant_id=sub.tenant_id,
        purpose=ChargePurpose.renewal,
        payment_method_id=pm.id,
        subscription_id=sub.id,
        amount=amount,
        idempotency_key=f"aeos-rn-{sub.tenant_id}-{sub.id}-{period_tag}-{attempt_no}",
        status=ChargeStatus.pending,
        attempt_no=attempt_no,
    )
    db.add(charge)
    db.flush()
    return charge


def create_renewal_invoice(
    db: Session, sub: TenantSubscription
) -> tuple[PaymentIntent, str | None]:
    from app.modules.billing.payment_service import (
        PERIOD_LABEL,
        TIER_LABEL,
        create_checkout_intent,
    )

    existing = _pending_invoice(db, sub)
    if existing is not None:
        return existing, existing.checkout_url
    amount, discount = renewal_price(sub)
    email = _payer_email(db, sub.tenant_id)
    return create_checkout_intent(
        db,
        tenant_id=sub.tenant_id,
        type=PaymentIntentType.renewal,
        amount=amount,
        payer_email=email,
        description=f"Perpanjangan langganan {TIER_LABEL[sub.tier]} "
        f"({PERIOD_LABEL[sub.billing_period]})",
        tier=sub.tier,
        billing_period=sub.billing_period,
        discount_percent=discount,
        subscription_id=sub.id,
    )


def _open_cycle_after_renewal(db: Session, sub: TenantSubscription) -> None:
    open_cycle = _get_open_cycle(db, sub.tenant_id)
    today = date.today()
    if open_cycle is not None and open_cycle.period_end >= today:
        return
    if open_cycle is not None:
        open_cycle.closed_at = datetime.now(UTC)
    from app.modules.billing.cycle_close import _add_months

    db.add(
        TenantBudgetCycle(
            tenant_id=sub.tenant_id,
            subscription_id=sub.id,
            period_start=today,
            period_end=_add_months(today, 1) - timedelta(days=1),
            included_budget=sub.included_budget,
            consumed=0,
        )
    )


def apply_renewal_success(
    db: Session,
    tenant_id: UUID,
    *,
    intent: PaymentIntent | None = None,
    charge: PaymentCharge | None = None,
    channel_label: str,
) -> TenantSubscription:
    """Perpanjang masa bayar dari jatuh tempo lama + kwitansi + ledger.
    Tanpa commit. Bila langganan sudah dibatalkan saat pembayaran masuk,
    diaktifkan ulang sebagai langganan baru dengan tier/periode yang sama."""
    from app.modules.billing import receipts
    from app.modules.billing.payment_service import (
        _activate_subscription,
        add_months,
        period_months,
        subscription_line,
    )

    sub_id = intent.subscription_id if intent else (charge.subscription_id if charge else None)
    sub = db.get(TenantSubscription, sub_id) if sub_id else current_subscription(db, tenant_id)
    amount = to_decimal(intent.amount if intent else (charge.amount if charge else 0))
    discount = (
        to_decimal(intent.discount_percent)
        if intent
        else to_decimal(sub.discount_percent if sub else 0)
    )
    if sub is None or sub.status == SubscriptionStatus.cancelled:
        tier = intent.tier if intent and intent.tier else (sub.tier if sub else None)
        if tier is None:
            raise HTTPException(
                status_code=500, detail="Renewal tanpa tier -- data tidak konsisten"
            )
        period = BillingPeriod(
            (intent.billing_period if intent else None)
            or (sub.billing_period.value if sub else BillingPeriod.monthly.value)
        )
        sub = _activate_subscription(
            db, tenant_id, tier, amount, billing_period=period, discount_percent=discount
        )
        start, new_end = date.today(), sub.current_period_end
    else:
        old_end = sub.current_period_end or date.today()
        start = old_end + timedelta(days=1)
        new_end = add_months(old_end, period_months(sub.billing_period))
        sub.current_period_end = new_end
        sub.status = SubscriptionStatus.active
        sub.past_due_since = None
        sub.renewal_attempt_count = 0
        sub.next_renewal_attempt_at = None
        sub.period_fee = amount
        sub.discount_percent = discount
        _open_cycle_after_renewal(db, sub)
    receipt = receipts.issue_receipt(
        db,
        tenant_id=tenant_id,
        lines=[subscription_line(sub.tier, sub.billing_period, amount, start, new_end, discount)],
        total=amount,
        payment_method_label=channel_label,
        provider_reference=intent.provider_invoice_id
        if intent
        else charge.provider_charge_id
        if charge
        else None,
        issued_at=now_utc(),
        intent=intent,
        charge=None if intent else charge,
    )
    db.flush()
    db.add(
        CreditTransaction(
            tenant_id=tenant_id,
            type=CreditTransactionType.subscription_renewal,
            amount=float(amount),
            ref_event="billing.subscription_renewed",
            ref_entity_type="tenant_subscription",
            ref_entity_id=str(sub.id),
            balance_after=total_remaining(db, tenant_id),
            receipt_id=receipt.id,
        )
    )
    audit_add(
        db,
        action="billing.subscription_renewed",
        entity_type="tenant_subscription",
        entity_id=sub.id,
        detail={"current_period_end": str(new_end), "amount": str(amount)},
        tenant_id=tenant_id,
    )
    return sub


def on_charge_success(db: Session, charge: PaymentCharge) -> None:
    from app.modules.billing.payment_methods import payment_method_label

    pm = db.get(TenantPaymentMethod, charge.payment_method_id)
    apply_renewal_success(
        db,
        charge.tenant_id,
        charge=charge,
        channel_label=payment_method_label(pm) if pm else "Metode bayar tersimpan",
    )


def mark_past_due(db: Session, sub: TenantSubscription, *, reason: str) -> None:
    if sub.status == SubscriptionStatus.past_due:
        return
    sub.status = SubscriptionStatus.past_due
    sub.past_due_since = now_utc()
    audit_add(
        db,
        action="billing.subscription_past_due",
        entity_type="tenant_subscription",
        entity_id=sub.id,
        detail={"reason": reason},
        tenant_id=sub.tenant_id,
    )
    notify_billing_users(
        db,
        sub.tenant_id,
        title="Langganan menunggak -- akses dihentikan",
        body="Perpanjangan langganan gagal dibayar. Akses modul dihentikan sampai tunggakan "
        "dibayar di halaman Pembayaran. Data Anda tetap aman.",
    )


def _schedule_retry(sub: TenantSubscription, attempt_no: int) -> None:
    sub.renewal_attempt_count = attempt_no
    since = as_aware(sub.past_due_since) or now_utc()
    if attempt_no <= len(RETRY_DAYS):
        sub.next_renewal_attempt_at = since + timedelta(days=RETRY_DAYS[attempt_no - 1])
    else:
        sub.next_renewal_attempt_at = None


def on_charge_failure(db: Session, charge: PaymentCharge, code: str) -> None:
    sub = db.get(TenantSubscription, charge.subscription_id) if charge.subscription_id else None
    if sub is None:
        return
    audit_add(
        db,
        action="billing.subscription_renewal_failed",
        entity_type="tenant_subscription",
        entity_id=sub.id,
        detail={"failure_code": code, "attempt_no": charge.attempt_no},
        tenant_id=sub.tenant_id,
    )
    if get_settings().billing_renewal_enforcement and sub.status != SubscriptionStatus.cancelled:
        mark_past_due(db, sub, reason=f"renewal_charge_failed:{code}")
        _schedule_retry(sub, charge.attempt_no)
    else:
        notify_billing_users(
            db,
            sub.tenant_id,
            title="Perpanjangan langganan gagal ditagih",
            body=f"Charge perpanjangan gagal ({code}). Bayar lewat halaman Pembayaran.",
        )


def cancel_subscription(db: Session, sub: TenantSubscription, *, reason: str) -> None:
    sub.status = SubscriptionStatus.cancelled
    sub.cancelled_at = now_utc()
    open_cycle = _get_open_cycle(db, sub.tenant_id)
    if open_cycle is not None:
        open_cycle.closed_at = now_utc()
    audit_add(
        db,
        action="billing.subscription_cancelled",
        entity_type="tenant_subscription",
        entity_id=sub.id,
        detail={"reason": reason},
        tenant_id=sub.tenant_id,
    )


def process_subscription(db: Session, sub: TenantSubscription, today: date | None = None) -> str:
    """Satu langkah state machine renewal untuk satu langganan. Return aksi."""
    from app.modules.billing import charges

    settings = get_settings()
    enforcement = settings.billing_renewal_enforcement
    today = today or date.today()
    if sub.current_period_end is None:
        return "skip_legacy"
    cpe = sub.current_period_end
    account = _get_or_create_credit_account(db, sub.tenant_id)
    pm = default_payment_method(db, account)

    if sub.status == SubscriptionStatus.active:
        if not sub.auto_renew:
            if today > cpe:
                cancel_subscription(db, sub, reason="auto_renew_off")
                db.commit()
                return "cancelled_no_renew"
            return "noop"
        if enforcement and pm is not None:
            if today <= cpe:
                return "noop"
            pending = _pending_charge(db, sub)
            if pending is not None:
                charges.execute_charge(db, pending.id)
                return "charge_reconciled"
            charge = create_renewal_charge(db, sub, pm, attempt_no=1)
            charge_id = charge.id
            db.commit()
            charges.execute_charge(db, charge_id)
            return "charged"
        if today >= cpe - timedelta(days=INVOICE_LEAD_DAYS):
            had_invoice = _pending_invoice(db, sub) is not None
            if not had_invoice:
                create_renewal_invoice(db, sub)
                fresh = db.get(TenantSubscription, sub.id)
                assert fresh is not None
                sub = fresh
                notify_billing_users(
                    db,
                    sub.tenant_id,
                    title="Tagihan perpanjangan langganan terbit",
                    body=f"Langganan berakhir {cpe.strftime('%d/%m/%Y')}. Bayar tagihan di "
                    "halaman Pembayaran agar akses tidak terhenti.",
                )
                db.commit()
            tolerance = timedelta(days=settings.billing_renewal_grace_days)
            if enforcement and today > cpe + tolerance:
                mark_past_due(db, sub, reason="renewal_invoice_unpaid")
                db.commit()
                return "past_due"
            return "invoiced" if not had_invoice else "noop"
        return "noop"

    if sub.status == SubscriptionStatus.past_due and enforcement:
        since = as_aware(sub.past_due_since) or now_utc()
        if today >= since.date() + timedelta(days=settings.billing_past_due_cancel_days):
            cancel_subscription(db, sub, reason="past_due_expired")
            db.commit()
            return "cancelled_past_due"
        next_at = as_aware(sub.next_renewal_attempt_at)
        if pm is not None and next_at is not None and next_at <= now_utc():
            pending = _pending_charge(db, sub)
            if pending is not None:
                charges.execute_charge(db, pending.id)
                return "charge_reconciled"
            charge = create_renewal_charge(db, sub, pm, attempt_no=sub.renewal_attempt_count + 1)
            charge_id = charge.id
            db.commit()
            charges.execute_charge(db, charge_id)
            return "retried"
    return "noop"


def run_renewals_for_all_tenants(db: Session, today: date | None = None) -> dict:
    """Cron harian. Iterasi `tenants` (tanpa RLS) lalu set_tenant per tenant."""
    from app.modules.platform.models import Tenant

    previous = get_tenant()
    tenant_ids = [row[0] for row in db.execute(select(Tenant.id)).all()]
    actions: dict[str, int] = {}
    try:
        for tenant_id in tenant_ids:
            set_tenant(tenant_id)
            sub = current_subscription(db, tenant_id)
            if sub is None:
                continue
            try:
                action = process_subscription(db, sub, today)
            except Exception:  # noqa: BLE001 - satu tenant gagal tidak menghentikan cron
                logger.exception("Renewal gagal diproses untuk tenant %s", tenant_id)
                db.rollback()
                action = "error"
            actions[action] = actions.get(action, 0) + 1
    finally:
        set_tenant(previous)
    return {"actions": actions}


def retry_renewal(db: Session, tenant_id: UUID, *, payment_method_id: UUID | None) -> dict:
    """Tenant membayar tunggakan/perpanjangan sekarang: charge metode bayar
    (yang dipilih atau default) bila ada, selain itu invoice."""
    from app.modules.billing import charges
    from app.modules.billing.models import PaymentMethodStatus

    sub = current_subscription(db, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Tidak ada langganan untuk diperpanjang")
    if sub.status == SubscriptionStatus.active and not (
        sub.current_period_end and date.today() >= sub.current_period_end - timedelta(days=7)
    ):
        raise HTTPException(status_code=409, detail="Langganan belum mendekati jatuh tempo")
    account = _get_or_create_credit_account(db, tenant_id)
    pm: TenantPaymentMethod | None
    if payment_method_id is not None:
        pm = db.get(TenantPaymentMethod, payment_method_id)
        if pm is None or pm.tenant_id != tenant_id or pm.status != PaymentMethodStatus.active:
            raise HTTPException(status_code=422, detail="Metode bayar tidak aktif")
    else:
        pm = default_payment_method(db, account)
    if pm is not None:
        pending = _pending_charge(db, sub)
        if pending is not None:
            result = charges.execute_charge(db, pending.id)
        else:
            charge = create_renewal_charge(db, sub, pm, attempt_no=sub.renewal_attempt_count + 1)
            charge_id = charge.id
            db.commit()
            result = charges.execute_charge(db, charge_id)
        return {
            "charge_id": str(result.id),
            "status": result.status.value,
            "checkout_url": None,
            "failure_code": result.failure_code,
        }
    # Invoice pending lama dipakai ulang (bukan diterbitkan dobel).
    intent, checkout_url = create_renewal_invoice(db, sub)
    return {
        "charge_id": None,
        "status": "invoice_created",
        "checkout_url": checkout_url,
        "intent_id": str(intent.id),
        "failure_code": None,
    }
