"""Router billing Opsi G (Fase 28 + lanjutan).

- `webhook_router`: dipanggil Xendit tanpa JWT -- keaslian diverifikasi lewat
  header `X-Callback-Token` (bukan JWT/guard lisensi), pola sama
  `esign/router.py::webhook_router`.
- `router` (guard `require_active_subscription()`): saldo, top-up, riwayat,
  pengaturan auto-reload -- butuh langganan aktif.
- `account_router` (guard `require_tenant_user()`, TANPA syarat langganan
  aktif): status, paket, subscribe, metode bayar, kwitansi, profil,
  perpanjangan. Tenant yang belum berlangganan atau MENUNGGAK harus tetap
  bisa membayar dan mengunduh kwitansi (aturan gagal bayar (e)).
- `sandbox_router`: simulasi gateway, hanya aktif bila PAYMENT_PROVIDER=sandbox
  dan APP_ENV != production (selain itu 404).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import BILLING_MANAGE_ROLES
from app.core.security import (
    get_current_user,
    require_active_subscription,
    require_roles,
    require_tenant_user,
)
from app.modules.billing import (
    payment_methods,
    payment_service,
    receipts,
    renewal,
    service,
    webhooks,
)
from app.modules.billing.models import (
    BillingPeriod,
    PaymentIntentType,
    PaymentMethodType,
    SubscriptionTier,
)

# Webhook Xendit: tanpa guard lisensi/subscription (dipanggil sistem eksternal).
webhook_router = APIRouter(prefix="/billing", tags=["billing"])

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    dependencies=[Depends(get_current_user), Depends(require_active_subscription())],
)

account_router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)
# Nama lama dipertahankan untuk kompatibilitas impor.
subscribe_router = account_router

_manage = [Depends(require_roles(*BILLING_MANAGE_ROLES))]


def _sandbox_enabled() -> None:
    settings = get_settings()
    if settings.payment_provider != "sandbox" or settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not Found")


sandbox_router = APIRouter(
    prefix="/billing/sandbox",
    tags=["billing-sandbox"],
    dependencies=[
        Depends(_sandbox_enabled),
        Depends(get_current_user),
        Depends(require_tenant_user()),
    ],
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class SubscribeIn(BaseModel):
    tier: SubscriptionTier
    billing_period: BillingPeriod = BillingPeriod.monthly


class TopupIn(BaseModel):
    amount: float = Field(gt=0)


class AutoReloadSettingsIn(BaseModel):
    enabled: bool
    threshold: float | None = Field(default=None, ge=0)
    # Diabaikan: nominal tetap Rp100.000 (K3). Diterima agar klien lama
    # yang masih mengirim `amount` tidak gagal validasi.
    amount: float | None = None


class PaymentMethodIn(BaseModel):
    # extra="forbid": field seperti `card_number`/`cvv` otomatis 422 --
    # backend TIDAK PERNAH menerima data kartu mentah.
    model_config = ConfigDict(extra="forbid")

    type: PaymentMethodType
    card_token_id: str | None = Field(default=None, max_length=200)


class BillingProfileIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    npwp: str | None = Field(default=None, max_length=22)
    address: str | None = Field(default=None, max_length=1000)
    billing_email: str | None = Field(default=None, max_length=255)


class SubscriptionPatchIn(BaseModel):
    auto_renew: bool


class RetryRenewalIn(BaseModel):
    payment_method_id: UUID | None = None


# ---------------------------------------------------------------------------
# Router langganan aktif
# ---------------------------------------------------------------------------


@router.get("/balance-summary")
def balance_summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant_id: UUID = user.tenant_id
    return service.get_balance_summary(db, tenant_id)


@router.post("/topup", dependencies=_manage)
def topup(payload: TopupIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    intent, checkout_url = payment_service.create_checkout_intent(
        db,
        tenant_id=user.tenant_id,
        type=PaymentIntentType.topup,
        amount=payload.amount,
        payer_email=user.email,
        description="Top up saldo kredit",
    )
    return {"intent_id": str(intent.id), "checkout_url": checkout_url}


@router.get("/auto-reload-settings")
def auto_reload_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.get_auto_reload_settings(db, user.tenant_id)


@router.put("/auto-reload-settings", dependencies=_manage)
def update_auto_reload_settings(
    payload: AutoReloadSettingsIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.update_auto_reload_settings(
        db, user.tenant_id, enabled=payload.enabled, threshold=payload.threshold
    )


@router.get("/transactions")
def transactions(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit harus 1-200")
    rows = service.list_transactions(db, user.tenant_id, limit=limit, offset=offset)
    return [
        {
            "id": str(t.id),
            "type": t.type.value,
            "amount": float(t.amount),
            "ref_event": t.ref_event,
            "balance_after": float(t.balance_after),
            "created_at": t.created_at,
            "receipt_id": str(t.receipt_id) if t.receipt_id else None,
        }
        for t in rows
    ]


# ---------------------------------------------------------------------------
# Router akun (tanpa syarat langganan aktif)
# ---------------------------------------------------------------------------


@account_router.get("/status")
def billing_status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.get_billing_status(db, user.tenant_id)


@account_router.get("/plans")
def plans():
    return service.list_plans()


@account_router.post("/subscribe", dependencies=_manage)
def subscribe(payload: SubscribeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    amount, discount = service.price_for(payload.tier, payload.billing_period)
    label = payment_service.TIER_LABEL[payload.tier]
    period_label = payment_service.PERIOD_LABEL[payload.billing_period]
    intent, checkout_url = payment_service.create_checkout_intent(
        db,
        tenant_id=user.tenant_id,
        type=PaymentIntentType.subscription,
        amount=amount,
        payer_email=user.email,
        description=f"Langganan {label} ({period_label})",
        tier=payload.tier,
        billing_period=payload.billing_period,
        discount_percent=discount,
    )
    return {
        "intent_id": str(intent.id),
        "checkout_url": checkout_url,
        "amount": float(amount),
        "billing_period": payload.billing_period.value,
        "discount_percent": float(discount),
    }


@account_router.patch("/subscription", dependencies=_manage)
def patch_subscription(
    payload: SubscriptionPatchIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    sub = service.current_subscription(db, user.tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Tenant belum berlangganan")
    if sub.auto_renew != payload.auto_renew:
        service.audit_add(
            db,
            action="billing.subscription_auto_renew_changed",
            entity_type="tenant_subscription",
            entity_id=sub.id,
            detail={"auto_renew": payload.auto_renew},
            tenant_id=user.tenant_id,
        )
        sub.auto_renew = payload.auto_renew
        db.commit()
    return service.get_billing_status(db, user.tenant_id)["subscription"]


@account_router.post("/subscription/retry-renewal", dependencies=_manage)
def retry_renewal(
    payload: RetryRenewalIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return renewal.retry_renewal(db, user.tenant_id, payment_method_id=payload.payment_method_id)


@account_router.get("/payment-config")
def payment_config():
    settings = get_settings()
    return {
        "provider": settings.payment_provider or None,
        "xendit_public_key": settings.xendit_public_key
        if settings.payment_provider == "xendit"
        else None,
        "supported_types": [t.value for t in PaymentMethodType],
    }


@account_router.get("/payment-methods", dependencies=_manage)
def list_payment_methods(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return payment_methods.list_payment_methods(db, user.tenant_id)


@account_router.post("/payment-methods", status_code=201, dependencies=_manage)
def add_payment_method(
    payload: PaymentMethodIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return payment_methods.add_payment_method(
        db,
        user.tenant_id,
        user_id=user.id,
        user_email=user.email,
        type=payload.type,
        card_token_id=payload.card_token_id,
    )


@account_router.post("/payment-methods/{payment_method_id}/default", dependencies=_manage)
def set_default_payment_method(
    payment_method_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return payment_methods.set_default(db, user.tenant_id, payment_method_id)


@account_router.delete(
    "/payment-methods/{payment_method_id}", status_code=204, dependencies=_manage
)
def delete_payment_method(
    payment_method_id: UUID,
    force: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    payment_methods.remove_payment_method(db, user.tenant_id, payment_method_id, force=force)
    return Response(status_code=204)


@account_router.get("/profile")
def get_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    profile = payment_methods.get_or_create_profile(db, user.tenant_id)
    db.commit()
    return payment_methods.profile_out(profile)


@account_router.put("/profile", dependencies=_manage)
def put_profile(
    payload: BillingProfileIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return payment_methods.update_profile(
        db,
        user.tenant_id,
        legal_name=payload.legal_name,
        npwp=payload.npwp,
        address=payload.address,
        billing_email=payload.billing_email,
    )


@account_router.get("/receipts", dependencies=_manage)
def list_receipts(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit harus 1-200")
    return receipts.list_receipts(db, user.tenant_id, limit=limit, offset=offset)


@account_router.get("/receipts/{receipt_id}/pdf", dependencies=_manage)
def download_receipt(
    receipt_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    from app.modules.billing.models import BillingReceipt

    receipt = db.get(BillingReceipt, receipt_id)
    if receipt is None or receipt.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    pdf, filename = receipts.get_receipt_pdf(db, receipt_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@webhook_router.post("/webhook/xendit")
async def xendit_webhook(request: Request, db: Session = Depends(get_db)):
    # Baca raw body dulu (konsisten dengan pola esign), meski verifikasi
    # Xendit sendiri berbasis header token, bukan HMAC-of-body.
    await request.body()
    payment_service.verify_xendit_webhook(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        return {"status": "ignored", "reason": "payload bukan objek"}
    return webhooks.handle_webhook(db, dict(request.headers), payload)


# ---------------------------------------------------------------------------
# Sandbox (simulasi gateway -- lewat jalur webhook yang SAMA)
# ---------------------------------------------------------------------------


@sandbox_router.post("/invoices/{provider_invoice_id}/pay")
def sandbox_pay_invoice(
    provider_invoice_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    intent = payment_service.find_intent(db, provider_invoice_id)
    if intent is None or intent.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan")
    payload = {
        "id": provider_invoice_id,
        "external_id": f"aeos-{intent.type.value}-{intent.tenant_id}-sandbox",
        "status": "PAID",
        "paid_at": date.today().isoformat(),
        "payment_channel": "SANDBOX",
    }
    return webhooks.handle_webhook(db, {}, payload)


def _sandbox_pm_event(db: Session, user, reference_id: str, status: str, event: str) -> dict:
    pm = payment_methods.find_by_reference(db, reference_id)
    if pm is None or pm.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Metode bayar tidak ditemukan")
    data: dict = {
        "id": pm.provider_payment_method_id,
        "reference_id": reference_id,
        "status": status,
    }
    if pm.type == PaymentMethodType.gopay:
        data["ewallet"] = {"account": {"account_details": "0812****7890"}}
    else:
        data["card"] = {
            "card_information": {
                "network": "VISA",
                "masked_card_number": "400000XXXXXX4242",
                "expiry_month": "12",
                "expiry_year": "2030",
            }
        }
    if status == "FAILED":
        data["failure_code"] = "AUTHENTICATION_FAILED"
    return webhooks.handle_webhook(db, {}, {"event": event, "data": data})


@sandbox_router.post("/payment-methods/{reference_id}/activate")
def sandbox_activate_pm(
    reference_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return _sandbox_pm_event(db, user, reference_id, "ACTIVE", "payment_method.activated")


@sandbox_router.post("/payment-methods/{reference_id}/fail")
def sandbox_fail_pm(
    reference_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return _sandbox_pm_event(db, user, reference_id, "FAILED", "payment_method.failed")


def _sandbox_charge_event(db: Session, user, charge_id: UUID, succeed: bool) -> dict:
    from app.core.payment.sandbox import sandbox_settle_charge
    from app.modules.billing.models import PaymentCharge

    charge = db.get(PaymentCharge, charge_id)
    if charge is None or charge.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Charge tidak ditemukan")
    result = sandbox_settle_charge(charge.idempotency_key, "succeeded" if succeed else "failed")
    data = {
        "payment_request_id": result.provider_charge_id,
        "reference_id": charge.idempotency_key,
        "status": "SUCCEEDED" if succeed else "FAILED",
    }
    if not succeed:
        data["failure_code"] = "CARD_DECLINED"
    event = "payment.succeeded" if succeed else "payment.failed"
    return webhooks.handle_webhook(db, {}, {"event": event, "data": data})


@sandbox_router.post("/charges/{charge_id}/succeed")
def sandbox_succeed_charge(
    charge_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return _sandbox_charge_event(db, user, charge_id, True)


@sandbox_router.post("/charges/{charge_id}/fail")
def sandbox_fail_charge(
    charge_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return _sandbox_charge_event(db, user, charge_id, False)
