"""Router billing Opsi G (Fase 28).

`webhook_router`: dipanggil Xendit tanpa JWT -- keaslian diverifikasi lewat
header `X-Callback-Token` (bukan JWT/guard lisensi), pola sama
`esign/router.py::webhook_router`. `router`: endpoint tenant-scoped, guard
`require_active_subscription()` (balance/topup/transactions -- perlu sudah
berlangganan). `subscribe_router`: guard lebih longgar `require_tenant_user()`
(tanpa require_active_subscription) khusus `/subscribe`, karena tenant
foundation-only yang BELUM berlangganan justru harus bisa memanggilnya.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_active_subscription, require_tenant_user
from app.modules.billing import payment_service, service
from app.modules.billing.models import TIER_MONTHLY_FEE_IDR, PaymentIntentType, SubscriptionTier

# Webhook Xendit: tanpa guard lisensi/subscription (dipanggil sistem eksternal).
webhook_router = APIRouter(prefix="/billing", tags=["billing"])

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    dependencies=[Depends(get_current_user), Depends(require_active_subscription())],
)

# Guard longgar khusus subscribe -- tenant foundation-only (belum
# berlangganan sama sekali) harus tetap bisa memanggil endpoint ini.
subscribe_router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)


class SubscribeIn(BaseModel):
    tier: SubscriptionTier


class TopupIn(BaseModel):
    amount: float = Field(gt=0)


@router.get("/balance-summary")
def balance_summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant_id: UUID = user.tenant_id
    return service.get_balance_summary(db, tenant_id)


@subscribe_router.post("/subscribe")
def subscribe(payload: SubscribeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    amount = TIER_MONTHLY_FEE_IDR[payload.tier]
    intent, checkout_url = payment_service.create_checkout_intent(
        db,
        tenant_id=user.tenant_id,
        type=PaymentIntentType.subscription,
        amount=amount,
        payer_email=user.email,
        description=f"Langganan {payload.tier.value}",
        tier=payload.tier,
    )
    return {"intent_id": str(intent.id), "checkout_url": checkout_url}


@router.post("/topup")
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
        }
        for t in rows
    ]


@webhook_router.post("/webhook/xendit")
async def xendit_webhook(request: Request, db: Session = Depends(get_db)):
    # Baca raw body dulu (konsisten dengan pola esign), meski verifikasi
    # Xendit sendiri berbasis header token, bukan HMAC-of-body.
    await request.body()
    payment_service.verify_xendit_webhook(request)
    payload = await request.json()
    provider_invoice_id = str(payload.get("id") or payload.get("external_id") or "").strip()
    if not provider_invoice_id:
        return {"status": "ignored", "reason": "invoice id tidak ditemukan di payload"}

    status = str(payload.get("status") or "").upper()
    if status not in ("PAID", "SETTLED"):
        return {"status": "ignored", "reason": f"status {status} bukan pelunasan"}

    intent = payment_service.reconcile_payment(db, provider_invoice_id)
    return {"status": "ok", "intent_id": str(intent.id)}
