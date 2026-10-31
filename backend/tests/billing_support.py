"""Utilitas bersama test billing Fase 28 lanjutan.

Semua test memakai `SandboxPaymentAdapter` (PAYMENT_PROVIDER=sandbox) atau
fake adapter yang di-monkeypatch -- TIDAK ada kredensial/vendor sungguhan.
Fixture `billing_env` mengisolasi env billing dari `.env` developer (diskon,
penegakan renewal, identitas penjual, storage) supaya test deterministik.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest
from app.core.config import get_settings

from tests.conftest import _auth_header
from tests.test_billing import _default_tenant_id, _seed_subscription_and_cycle, _set_commercial

WEBHOOK_TOKEN = "test-xendit-webhook-token"


@pytest.fixture()
def billing_env(monkeypatch, tmp_path):
    settings = get_settings()
    values = {
        "payment_provider": "sandbox",
        "xendit_webhook_token": WEBHOOK_TOKEN,
        "xendit_public_key": None,
        "billing_annual_discount_percent": None,
        "billing_renewal_enforcement": False,
        "billing_renewal_grace_days": 0,
        "billing_renewal_processing_days": 1,
        "billing_past_due_cancel_days": 30,
        "billing_auto_reload_default_threshold": None,
        "aeos_seller_name": "PT Aeos Teknologi",
        "aeos_seller_npwp": "01.234.567.8-901.000",
        "aeos_seller_address": "Jakarta",
        "aeos_seller_email": "billing@aeos.test",
        "aeos_seller_is_pkp": False,
        "billing_ppn_rate": None,
        "storage_endpoint": None,
        "data_dir": str(tmp_path),
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    return settings


def setup_tenant(client, *, cycle_included: float = 1_000_000) -> tuple[dict, str]:
    """Admin + tenant default komersial + langganan aktif & siklus terbuka."""
    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=cycle_included)
    return admin, tenant_id


def add_card(client, admin: dict, token: str = "sbx-tok-ok") -> dict:
    resp = client.post(
        "/api/v1/billing/payment-methods",
        headers=admin,
        json={"type": "card", "card_token_id": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def enable_auto_reload(client, admin: dict, threshold: float = 50_000) -> dict:
    resp = client.put(
        "/api/v1/billing/auto-reload-settings",
        headers=admin,
        json={"enabled": True, "threshold": threshold},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def set_balances(client, tenant_id: str, *, cycle_remaining: float, credit: float) -> None:
    """Atur sisa jatah siklus terbuka & saldo top-up langsung via DB."""
    from app.core.tenancy import set_tenant
    from app.modules.billing.service import _get_open_cycle, _get_or_create_credit_account

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        cycle = _get_open_cycle(db, tid)
        assert cycle is not None
        cycle.consumed = float(cycle.included_budget) - cycle_remaining
        account = _get_or_create_credit_account(db, tid)
        account.balance = credit
        db.commit()
    finally:
        set_tenant(None)
        db.close()


def run_in_tenant(client, tenant_id: str, fn):
    """Jalankan `fn(db)` di konteks tenant (sesi test baru), kembalikan hasilnya."""
    from app.core.tenancy import set_tenant

    db = client.testing_session()
    try:
        set_tenant(UUID(tenant_id))
        return fn(db)
    finally:
        set_tenant(None)
        db.close()


def webhook(client, payload: dict, headers: dict | None = None):
    hdrs = {"X-Callback-Token": WEBHOOK_TOKEN}
    hdrs.update(headers or {})
    return client.post("/api/v1/billing/webhook/xendit", headers=hdrs, json=payload)


def set_period_end(client, tenant_id: str, days_from_today: int) -> None:
    def _apply(db):
        from app.modules.billing.service import current_subscription

        sub = current_subscription(db, UUID(tenant_id))
        assert sub is not None
        sub.current_period_end = date.today() + timedelta(days=days_from_today)
        db.commit()

    run_in_tenant(client, tenant_id, _apply)
