"""Fase 28: adapter pembayaran Xendit (mode sandbox) + rekonsiliasi webhook.

Tidak butuh vendor sungguhan: PAYMENT_PROVIDER di-patch ke "sandbox" (pola
sama `tests/test_esign.py`) dan webhook diverifikasi lewat header
X-Callback-Token statis, bukan panggilan API Xendit nyata.
"""

from unittest.mock import patch
from uuid import UUID

from app.core.config import get_settings

from tests.conftest import _auth_header
from tests.test_billing import _default_tenant_id, _set_commercial

_WEBHOOK_TOKEN = "test-xendit-webhook-token"


def _sandbox_settings():
    settings = get_settings()
    return (
        patch.object(settings, "payment_provider", "sandbox"),
        patch.object(settings, "xendit_webhook_token", _WEBHOOK_TOKEN),
    )


def test_get_adapter_without_provider_returns_503(client):
    from app.modules.billing.payment_service import get_adapter
    from fastapi import HTTPException

    settings = get_settings()
    with patch.object(settings, "payment_provider", ""):
        try:
            get_adapter()
            raise AssertionError("expected HTTPException")
        except HTTPException as exc:
            assert exc.status_code == 503


def test_subscription_checkout_and_webhook_activates_subscription(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.models import (
        PaymentIntentStatus,
        PaymentIntentType,
        SubscriptionStatus,
        SubscriptionTier,
        TenantSubscription,
    )
    from app.modules.billing.payment_service import create_checkout_intent
    from sqlalchemy import select

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)

    p1, p2 = _sandbox_settings()
    with p1, p2:
        db = client.testing_session()
        try:
            tid = UUID(tenant_id)
            set_tenant(tid)
            intent, checkout_url = create_checkout_intent(
                db,
                tenant_id=tid,
                type=PaymentIntentType.subscription,
                amount=500_000,
                payer_email="admin@example.com",
                description="Langganan Tier 1",
                tier=SubscriptionTier.tier1,
            )
            assert checkout_url is not None
            assert intent.status == PaymentIntentStatus.pending
            invoice_id = intent.provider_invoice_id
        finally:
            set_tenant(None)
            db.close()

        resp = client.post(
            "/api/v1/billing/webhook/xendit",
            headers={"X-Callback-Token": _WEBHOOK_TOKEN},
            json={"id": invoice_id, "external_id": invoice_id, "status": "PAID"},
        )
        assert resp.status_code == 200, resp.text

        db = client.testing_session()
        try:
            tid = UUID(tenant_id)
            set_tenant(tid)
            sub = db.execute(
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tid)
                .where(TenantSubscription.status == SubscriptionStatus.active)
            ).scalar_one_or_none()
            assert sub is not None
            assert sub.tier == SubscriptionTier.tier1
        finally:
            set_tenant(None)
            db.close()


def test_webhook_wrong_token_rejected(client):
    _auth_header(client)
    p1, p2 = _sandbox_settings()
    with p1, p2:
        resp = client.post(
            "/api/v1/billing/webhook/xendit",
            headers={"X-Callback-Token": "salah"},
            json={"id": "sbx-pay-xxxx", "status": "PAID"},
        )
        assert resp.status_code == 401


def test_topup_webhook_credits_account(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.models import PaymentIntentType, TenantCreditAccount
    from app.modules.billing.payment_service import create_checkout_intent
    from sqlalchemy import select

    from tests.test_billing import _seed_subscription_and_cycle

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    p1, p2 = _sandbox_settings()
    with p1, p2:
        db = client.testing_session()
        try:
            tid = UUID(tenant_id)
            set_tenant(tid)
            intent, _url = create_checkout_intent(
                db,
                tenant_id=tid,
                type=PaymentIntentType.topup,
                amount=200_000,
                payer_email="admin@example.com",
                description="Top up saldo",
            )
            invoice_id = intent.provider_invoice_id
        finally:
            set_tenant(None)
            db.close()

        resp = client.post(
            "/api/v1/billing/webhook/xendit",
            headers={"X-Callback-Token": _WEBHOOK_TOKEN},
            json={"id": invoice_id, "status": "PAID"},
        )
        assert resp.status_code == 200, resp.text

        # Webhook kedua (retry Xendit) -- idempotent, tidak menggandakan saldo.
        resp2 = client.post(
            "/api/v1/billing/webhook/xendit",
            headers={"X-Callback-Token": _WEBHOOK_TOKEN},
            json={"id": invoice_id, "status": "PAID"},
        )
        assert resp2.status_code == 200, resp2.text

        db = client.testing_session()
        try:
            tid = UUID(tenant_id)
            set_tenant(tid)
            account = db.execute(
                select(TenantCreditAccount).where(TenantCreditAccount.tenant_id == tid)
            ).scalar_one_or_none()
            assert account is not None
            assert float(account.balance) == 200_000
        finally:
            set_tenant(None)
            db.close()


def test_subscribe_endpoint_works_for_foundation_only_tenant(client):
    """`/subscribe` sengaja pakai guard `require_tenant_user()` (bukan
    `require_active_subscription()`) -- tenant foundation-only (belum
    punya TenantSubscription sama sekali) harus tetap bisa memanggilnya."""
    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)  # tanpa subscription apa pun sejauh ini

    p1, p2 = _sandbox_settings()
    with p1, p2:
        resp = client.post("/api/v1/billing/subscribe", headers=admin, json={"tier": "tier1"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["checkout_url"] is not None


def test_topup_endpoint_blocked_without_active_subscription(client):
    """`/topup` pakai guard ketat `require_active_subscription()` --
    tenant tanpa langganan aktif harus 403, bukan lolos ke Xendit."""
    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)

    p1, p2 = _sandbox_settings()
    with p1, p2:
        resp = client.post("/api/v1/billing/topup", headers=admin, json={"amount": 50_000})
        assert resp.status_code == 403, resp.text


def test_transactions_endpoint_returns_history_newest_first(client):
    from tests.test_billing import _seed_subscription_and_cycle

    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    cid = client.post(
        "/api/v1/clients", headers=admin, json={"name": "PT Riwayat Transaksi"}
    ).json()["id"]
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={
            "client_id": cid,
            "title": "Test Riwayat",
            "headcount": 1,
            "salary_min": 4_000_000,
            "salary_max": 5_000_000,
        },
    ).json()
    client.post(f"/api/v1/recruitment/job-orders/{jo['id']}/match", headers=admin)
    client.post(f"/api/v1/recruitment/job-orders/{jo['id']}/match", headers=admin)

    resp = client.get("/api/v1/billing/transactions", headers=admin)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) >= 2
    assert rows[0]["ref_event"] == "recruitment.match_executed"
    created_at = [r["created_at"] for r in rows]
    assert created_at == sorted(created_at, reverse=True)
