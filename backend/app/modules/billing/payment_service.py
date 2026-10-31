"""Factory adapter pembayaran, verifikasi webhook Xendit, dan rekonsiliasi
checkout -> efek bisnis (Fase 28). Factory mirror persis pola
`esign/service.py::get_adapter()`.
"""

from __future__ import annotations

import hmac
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.money import to_decimal
from app.core.payment.base import CheckoutResult, PaymentAdapter
from app.core.payment.sandbox import SandboxPaymentAdapter
from app.core.payment.xendit import XenditAdapter
from app.core.tenancy import get_tenant, set_tenant
from app.modules.billing.models import (
    TIER_MONTHLY_FEE_IDR,
    BillingPeriod,
    CreditTransaction,
    CreditTransactionType,
    PaymentIntent,
    PaymentIntentStatus,
    PaymentIntentType,
    SubscriptionStatus,
    SubscriptionTier,
    TenantBudgetCycle,
    TenantSubscription,
)
from app.modules.billing.service import (
    _get_open_cycle,
    audit_add,
    record_credit_transaction,
)

TIER_LABEL = {
    SubscriptionTier.tier1: "Tier 1",
    SubscriptionTier.tier2: "Tier 2",
    SubscriptionTier.tier3: "Tier 3",
}
PERIOD_LABEL = {BillingPeriod.monthly: "Bulanan", BillingPeriod.annual: "Tahunan"}


def get_adapter() -> PaymentAdapter:
    settings = get_settings()
    if settings.payment_provider == "sandbox":
        return SandboxPaymentAdapter()
    if settings.payment_provider == "xendit":
        return XenditAdapter()
    raise HTTPException(
        status_code=503,
        detail="Integrasi pembayaran belum aktif. Set PAYMENT_PROVIDER (sandbox/xendit) di .env.",
    )


def verify_xendit_webhook(request: Request) -> None:
    """Xendit memverifikasi webhook lewat header `X-Callback-Token` dibanding
    token statis di dashboard -- BUKAN skema HMAC-of-body seperti
    `esign_webhook_secret`/`_verify_webhook_secret` (Privy). Jangan disamakan.
    """
    token = request.headers.get("X-Callback-Token") or ""
    expected = get_settings().xendit_webhook_token or ""
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Token webhook tidak valid")


def add_months(d: date, months: int) -> date:
    from app.modules.billing.cycle_close import _add_months

    return _add_months(d, months)


def period_months(period: BillingPeriod) -> int:
    return 12 if period == BillingPeriod.annual else 1


def create_checkout_intent(
    db: Session,
    *,
    tenant_id: UUID,
    type: PaymentIntentType,
    amount: float | Decimal,
    payer_email: str,
    description: str,
    tier: SubscriptionTier | None = None,
    billing_period: BillingPeriod | None = None,
    discount_percent: Decimal | None = None,
    subscription_id: UUID | None = None,
) -> tuple[PaymentIntent, str | None]:
    """Buat invoice di gateway + catat `PaymentIntent` penanda janji bayar.
    Dipanggil dari endpoint self-service tenant (Milestone 7: subscribe/topup)
    dan cron renewal (invoice renewal tanpa metode bayar tersimpan).

    Transaksi DB ditutup dulu sebelum memanggil gateway (tidak ada transaksi
    terbuka selama HTTP); intent baru ditulis setelah invoice terbit.
    """
    adapter = get_adapter()
    external_id = f"aeos-{type.value}-{tenant_id}-{uuid4().hex[:8]}"
    db.commit()
    result: CheckoutResult = adapter.create_invoice(
        external_id=external_id,
        amount=float(amount),
        description=description,
        payer_email=payer_email,
    )
    intent = PaymentIntent(
        tenant_id=tenant_id,
        type=type,
        tier=tier,
        amount=float(amount),
        provider_invoice_id=result.provider_invoice_id,
        billing_period=billing_period.value if billing_period else None,
        discount_percent=discount_percent,
        subscription_id=subscription_id,
        checkout_url=result.checkout_url,
    )
    db.add(intent)
    if type in (PaymentIntentType.subscription, PaymentIntentType.renewal):
        audit_add(
            db,
            action="billing.subscription_checkout_created",
            entity_type="payment_intent",
            entity_id=intent.id,
            detail={
                "type": type.value,
                "tier": tier.value if tier else None,
                "billing_period": billing_period.value if billing_period else None,
                "discount_percent": str(discount_percent) if discount_percent is not None else None,
                "amount": str(amount),
            },
            tenant_id=tenant_id,
        )
    db.commit()
    db.refresh(intent)
    return intent, result.checkout_url


def _activate_subscription(
    db: Session,
    tenant_id: UUID,
    tier: SubscriptionTier,
    amount: float | Decimal,
    *,
    billing_period: BillingPeriod = BillingPeriod.monthly,
    discount_percent: Decimal | None = None,
    set_period_end: bool = True,
    current_period_end: date | None = None,
) -> TenantSubscription:
    """Ganti subscription aktif/menunggak (bila ada) dengan yang baru + buka
    cycle pertamanya. Tier switch = cutover langsung, bukan prorata --
    konsisten dengan keputusan "tidak ada grandfathering" di keputusan migrasi
    Fase 28. Jatah siklus SELALU bulanan (harga tier bulanan), termasuk untuk
    paket tahunan. `set_period_end=False` (override platform tanpa tanggal)
    = baris legacy yang tidak dikunci penegakan renewal."""
    existing_rows = db.execute(
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .where(
            TenantSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.past_due])
        )
    ).scalars()
    for existing in existing_rows:
        existing.status = SubscriptionStatus.cancelled
        existing.cancelled_at = datetime.now(UTC)
    open_cycle = _get_open_cycle(db, tenant_id)
    if open_cycle is not None:
        open_cycle.closed_at = datetime.now(UTC)

    monthly_fee = TIER_MONTHLY_FEE_IDR[tier]
    today = date.today()
    first_cycle_end = today + timedelta(days=30)
    if current_period_end is None and set_period_end:
        current_period_end = (
            add_months(today, 12) if billing_period == BillingPeriod.annual else first_cycle_end
        )
    subscription = TenantSubscription(
        tenant_id=tenant_id,
        tier=tier,
        monthly_fee=monthly_fee,
        included_budget=monthly_fee,
        status=SubscriptionStatus.active,
        billing_period=billing_period,
        period_fee=to_decimal(amount),
        discount_percent=discount_percent or Decimal(0),
        current_period_end=current_period_end,
    )
    db.add(subscription)
    db.flush()

    cycle = TenantBudgetCycle(
        tenant_id=tenant_id,
        subscription_id=subscription.id,
        period_start=today,
        period_end=first_cycle_end,
        included_budget=monthly_fee,
        consumed=0,
    )
    db.add(cycle)
    audit_add(
        db,
        action="billing.subscription_activated",
        entity_type="tenant_subscription",
        entity_id=subscription.id,
        detail={
            "tier": tier.value,
            "billing_period": billing_period.value,
            "period_fee": str(amount),
            "current_period_end": str(current_period_end) if current_period_end else None,
        },
        tenant_id=tenant_id,
    )
    return subscription


def subscription_line(
    tier: SubscriptionTier,
    period: BillingPeriod,
    amount: Decimal,
    start: date,
    end: date | None,
    discount: Decimal | None,
) -> dict:
    span = f" {start.strftime('%d/%m/%Y')}-{end.strftime('%d/%m/%Y')}" if end else ""
    label = f"Langganan Aeos {TIER_LABEL[tier]} - {PERIOD_LABEL[period]}{span}"
    if discount:
        label += f" (diskon {discount.normalize()}%)"
    return {"description": label, "qty": 1, "unit_price": str(amount), "amount": str(amount)}


def _claim_intent(db: Session, intent_id: UUID, paid_at: datetime) -> bool:
    """Compare-and-set `pending -> paid`. True hanya untuk pemanggil yang
    benar-benar memindahkan status (perbaikan race G7: dua webhook paralel
    tidak bisa sama-sama mengaktifkan langganan / mengkredit top-up)."""
    result = db.execute(
        update(PaymentIntent)
        .where(PaymentIntent.id == intent_id, PaymentIntent.status == PaymentIntentStatus.pending)
        .values(status=PaymentIntentStatus.paid, paid_at=paid_at)
        .execution_options(synchronize_session=False)
    )
    return getattr(result, "rowcount", 0) == 1


def find_intent(db: Session, provider_invoice_id: str) -> PaymentIntent | None:
    """Lookup TANPA konteks tenant aktif (tabel tanpa RLS, lihat migrasi
    e1f2a3b4c5d6) -- tenant di-set segera setelah baris ditemukan."""
    return db.execute(
        select(PaymentIntent)
        .where(PaymentIntent.provider_invoice_id == provider_invoice_id)
        .execution_options(include_with_loader_criteria=False)
    ).scalar_one_or_none()


def reconcile_payment(
    db: Session,
    provider_invoice_id: str,
    *,
    payment_channel_label: str | None = None,
    commit: bool = True,
) -> PaymentIntent:
    """Dipanggil dari webhook Xendit setelah verifikasi token. Baris
    `payment_intents` dicari TANPA konteks tenant aktif (lihat catatan RLS
    di migration-nya) -- tenant di-set SEGERA setelah baris ditemukan,
    sebelum menyentuh tabel ber-RLS lain (`TenantSubscription` dkk),
    mirip pola `payroll/service.py::decide_by_token`.

    Efek (aktivasi/top-up/renewal + kwitansi) hanya dijalankan oleh pemanggil
    yang memenangkan compare-and-set status -- idempoten terhadap webhook
    berulang maupun paralel.
    """
    intent = find_intent(db, provider_invoice_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Payment intent tidak ditemukan")
    if intent.status == PaymentIntentStatus.paid:
        return intent  # idempotent -- webhook boleh terkirim berulang

    previous_tenant = get_tenant()
    set_tenant(intent.tenant_id)
    try:
        paid_at = datetime.now(UTC)
        if not _claim_intent(db, intent.id, paid_at):
            db.refresh(intent)
            return intent
        intent.status = PaymentIntentStatus.paid
        intent.paid_at = paid_at
        _apply_intent_effect(db, intent, payment_channel_label or "Invoice Xendit")
        if commit:
            db.commit()
            db.refresh(intent)
        return intent
    finally:
        set_tenant(previous_tenant)


def _apply_intent_effect(db: Session, intent: PaymentIntent, channel_label: str) -> None:
    from app.modules.billing import receipts

    amount = to_decimal(intent.amount)
    paid_at = intent.paid_at or datetime.now(UTC)
    if intent.type == PaymentIntentType.subscription:
        if intent.tier is None:
            # Tidak boleh terjadi -- satu-satunya pemanggil `create_checkout_intent`
            # dengan type=subscription (endpoint /subscribe) selalu mengisi tier
            # (SubscribeIn.tier wajib, bukan Optional). Kalau ini terpicu berarti
            # ada jalur baru yang melanggar invariant itu.
            raise HTTPException(
                status_code=500,
                detail="Payment intent subscription tanpa tier -- data tidak konsisten",
            )
        period = BillingPeriod(intent.billing_period or BillingPeriod.monthly.value)
        subscription = _activate_subscription(
            db,
            intent.tenant_id,
            intent.tier,
            amount,
            billing_period=period,
            discount_percent=intent.discount_percent,
        )
        receipt = receipts.issue_receipt(
            db,
            tenant_id=intent.tenant_id,
            lines=[
                subscription_line(
                    intent.tier,
                    period,
                    amount,
                    date.today(),
                    subscription.current_period_end,
                    intent.discount_percent,
                )
            ],
            total=amount,
            payment_method_label=channel_label,
            provider_reference=intent.provider_invoice_id,
            issued_at=paid_at,
            intent=intent,
        )
        # Catatan histori pembayaran langganan -- bukan debit/kredit pool
        # (dana subscription MEMBENTUK cycle baru, bukan menambah saldo top-up),
        # tapi tetap layak muncul di riwayat transaksi tenant (Milestone 7 UI).
        db.add(
            CreditTransaction(
                tenant_id=intent.tenant_id,
                type=CreditTransactionType.subscription_charge,
                amount=float(amount),
                ref_event="billing.subscription_activated",
                ref_entity_type="tenant_subscription",
                ref_entity_id=str(subscription.id),
                balance_after=float(TIER_MONTHLY_FEE_IDR[intent.tier]),
                receipt_id=receipt.id,
            )
        )
    elif intent.type == PaymentIntentType.renewal:
        from app.modules.billing import renewal

        renewal.apply_renewal_success(
            db, intent.tenant_id, intent=intent, channel_label=channel_label
        )
    else:
        receipt = receipts.issue_receipt(
            db,
            tenant_id=intent.tenant_id,
            lines=[
                {
                    "description": "Top up saldo kredit Aeos",
                    "qty": 1,
                    "unit_price": str(amount),
                    "amount": str(amount),
                }
            ],
            total=amount,
            payment_method_label=channel_label,
            provider_reference=intent.provider_invoice_id,
            issued_at=paid_at,
            intent=intent,
        )
        record_credit_transaction(
            db,
            amount=float(amount),
            ref_event="billing.topup",
            ref_entity_type="payment_intent",
            ref_entity_id=str(intent.id),
            allow_negative=True,
            receipt_id=receipt.id,
        )


def expire_intent(db: Session, provider_invoice_id: str) -> bool:
    """Invoice kedaluwarsa: `pending -> expired` saja (status terminal `paid`
    tidak pernah ditimpa event yang datang terlambat)."""
    intent = find_intent(db, provider_invoice_id)
    if intent is None:
        return False
    result = db.execute(
        update(PaymentIntent)
        .where(PaymentIntent.id == intent.id, PaymentIntent.status == PaymentIntentStatus.pending)
        .values(status=PaymentIntentStatus.expired)
        .execution_options(synchronize_session=False)
    )
    return getattr(result, "rowcount", 0) == 1
