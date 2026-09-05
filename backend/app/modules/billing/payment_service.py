"""Factory adapter pembayaran, verifikasi webhook Xendit, dan rekonsiliasi
checkout -> efek bisnis (Fase 28). Factory mirror persis pola
`esign/service.py::get_adapter()`.
"""

from __future__ import annotations

import hmac
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.payment.base import CheckoutResult, PaymentAdapter
from app.core.payment.sandbox import SandboxPaymentAdapter
from app.core.payment.xendit import XenditAdapter
from app.core.tenancy import get_tenant, set_tenant
from app.modules.billing.models import (
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
from app.modules.billing.service import _get_open_cycle, record_credit_transaction


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


def create_checkout_intent(
    db: Session,
    *,
    tenant_id: UUID,
    type: PaymentIntentType,
    amount: float,
    payer_email: str,
    description: str,
    tier: SubscriptionTier | None = None,
) -> tuple[PaymentIntent, str | None]:
    """Buat invoice di gateway + catat `PaymentIntent` penanda janji bayar.
    Dipanggil dari endpoint self-service tenant (Milestone 7: subscribe/topup).
    """
    adapter = get_adapter()
    external_id = f"aeos-{type.value}-{tenant_id}-{uuid4().hex[:8]}"
    result: CheckoutResult = adapter.create_invoice(
        external_id=external_id,
        amount=amount,
        description=description,
        payer_email=payer_email,
    )
    intent = PaymentIntent(
        tenant_id=tenant_id,
        type=type,
        tier=tier,
        amount=amount,
        provider_invoice_id=result.provider_invoice_id,
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent, result.checkout_url


def _activate_subscription(
    db: Session, tenant_id: UUID, tier: SubscriptionTier, amount: float
) -> None:
    """Ganti subscription aktif (bila ada) dengan yang baru + buka cycle
    pertamanya. Tier switch = cutover langsung, bukan prorata -- konsisten
    dengan keputusan "tidak ada grandfathering" di keputusan migrasi Fase 28."""
    existing = db.execute(
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .where(TenantSubscription.status == SubscriptionStatus.active)
    ).scalar_one_or_none()
    if existing is not None:
        existing.status = SubscriptionStatus.cancelled
        existing.cancelled_at = datetime.now(UTC)
        open_cycle = _get_open_cycle(db, tenant_id)
        if open_cycle is not None:
            open_cycle.closed_at = datetime.now(UTC)

    subscription = TenantSubscription(
        tenant_id=tenant_id,
        tier=tier,
        monthly_fee=amount,
        included_budget=amount,
        status=SubscriptionStatus.active,
    )
    db.add(subscription)
    db.flush()

    today = date.today()
    cycle = TenantBudgetCycle(
        tenant_id=tenant_id,
        subscription_id=subscription.id,
        period_start=today,
        period_end=today + timedelta(days=30),
        included_budget=amount,
        consumed=0,
    )
    db.add(cycle)

    # Catatan histori pembayaran langganan -- bukan debit/kredit pool
    # (dana subscription MEMBENTUK cycle baru, bukan menambah saldo top-up),
    # tapi tetap layak muncul di riwayat transaksi tenant (Milestone 7 UI).
    db.add(
        CreditTransaction(
            tenant_id=tenant_id,
            type=CreditTransactionType.subscription_charge,
            amount=amount,
            ref_event="billing.subscription_activated",
            ref_entity_type="tenant_subscription",
            ref_entity_id=str(subscription.id),
            balance_after=amount,
        )
    )


def reconcile_payment(db: Session, provider_invoice_id: str) -> PaymentIntent:
    """Dipanggil dari webhook Xendit setelah verifikasi token. Baris
    `payment_intents` dicari TANPA konteks tenant aktif (lihat catatan RLS
    di migration-nya) -- tenant di-set SEGERA setelah baris ditemukan,
    sebelum menyentuh tabel ber-RLS lain (`TenantSubscription` dkk),
    mirip pola `payroll/service.py::decide_by_token`.
    """
    intent = db.execute(
        select(PaymentIntent)
        .where(PaymentIntent.provider_invoice_id == provider_invoice_id)
        .execution_options(include_with_loader_criteria=False)
    ).scalar_one_or_none()
    if intent is None:
        raise HTTPException(status_code=404, detail="Payment intent tidak ditemukan")
    if intent.status == PaymentIntentStatus.paid:
        return intent  # idempotent -- webhook boleh terkirim berulang

    previous_tenant = get_tenant()
    set_tenant(intent.tenant_id)
    try:
        intent.status = PaymentIntentStatus.paid
        intent.paid_at = datetime.now(UTC)

        if intent.type == PaymentIntentType.subscription:
            _activate_subscription(db, intent.tenant_id, intent.tier, float(intent.amount))
        else:
            record_credit_transaction(
                db,
                amount=float(intent.amount),
                ref_event="billing.topup",
                ref_entity_type="payment_intent",
                ref_entity_id=str(intent.id),
                allow_negative=True,
            )
        db.commit()
        db.refresh(intent)
        return intent
    finally:
        set_tenant(previous_tenant)
