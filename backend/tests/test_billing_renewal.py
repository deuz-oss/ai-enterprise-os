"""Fase 28 lanjutan: renewal & aturan gagal bayar (rencana §13 kasus 41-48)."""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from tests.billing_support import (  # noqa: F401 - fixture
    add_card,
    billing_env,
    run_in_tenant,
    set_balances,
    set_period_end,
    webhook,
)
from tests.conftest import _auth_header, _platform_admin_header
from tests.test_billing import _default_tenant_id, _set_commercial


def _paid_tenant(client, tier: str = "tier1") -> tuple[dict, str]:
    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    resp = client.post("/api/v1/billing/subscribe", headers=admin, json={"tier": tier})
    assert resp.status_code == 200, resp.text
    webhook(client, {"id": resp.json()["checkout_url"].split("/")[3], "status": "PAID"})
    return admin, tenant_id


def _sub(client, tenant_id):
    from app.modules.billing.models import TenantSubscription

    return run_in_tenant(
        client,
        tenant_id,
        lambda db: list(
            db.execute(select(TenantSubscription).order_by(TenantSubscription.started_at)).scalars()
        ),
    )


def _run_renewals(client) -> dict:
    resp = client.post(
        "/api/v1/platform/internal/run-renewals", headers=_platform_admin_header(client)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_flag_mati_hanya_invoice_tanpa_kunci(client, billing_env):  # noqa: F811
    """#41"""
    from app.modules.billing.models import PaymentIntent, PaymentIntentType

    admin, tenant_id = _paid_tenant(client)
    set_period_end(client, tenant_id, -1)
    assert client.get("/api/v1/billing/balance-summary", headers=admin).status_code == 200
    result = _run_renewals(client)
    assert result["actions"].get("invoiced") == 1
    intents = run_in_tenant(
        client,
        tenant_id,
        lambda db: list(
            db.execute(
                select(PaymentIntent).where(PaymentIntent.type == PaymentIntentType.renewal)
            ).scalars()
        ),
    )
    assert len(intents) == 1 and intents[0].checkout_url
    assert client.get("/api/v1/billing/balance-summary", headers=admin).status_code == 200
    _run_renewals(client)  # idempoten: tidak menerbitkan invoice kedua
    assert _sub(client, tenant_id)[-1].status.value == "aktif"


def test_renewal_gagal_menunggak_dan_akun_tetap_terbuka(client, billing_env, monkeypatch):  # noqa: F811
    """#42 + #43 charge renewal ditolak -> menunggak; modul bisnis 403
    subscription_past_due, endpoint akun billing tetap 200; retry dengan kartu
    lain sukses -> aktif, masa diperpanjang dari jatuh tempo lama."""
    from app.modules.billing.cycle_close import _add_months

    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", True)
    admin, tenant_id = _paid_tenant(client)
    add_card(client, admin, "sbx-tok-decline")
    set_period_end(client, tenant_id, -1)
    old_end = date.today() - timedelta(days=1)
    assert _run_renewals(client)["actions"].get("charged") == 1
    sub = _sub(client, tenant_id)[-1]
    assert sub.status.value == "menunggak"
    assert sub.next_renewal_attempt_at is not None

    blocked = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert blocked.status_code == 403
    assert blocked.headers.get("X-Error-Code") == "subscription_past_due"
    for path in ("/status", "/payment-methods", "/receipts", "/plans", "/profile"):
        assert client.get(f"/api/v1/billing{path}", headers=admin).status_code == 200, path
    status = client.get("/api/v1/billing/status", headers=admin).json()
    assert status["access"] == "none" and status["block_reason"] == "subscription_past_due"

    good = add_card(client, admin, "sbx-tok-ok")
    retry = client.post(
        "/api/v1/billing/subscription/retry-renewal",
        headers=admin,
        json={"payment_method_id": good["id"]},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "succeeded"
    sub = _sub(client, tenant_id)[-1]
    assert sub.status.value == "aktif"
    assert sub.current_period_end == _add_months(old_end, 1)
    assert client.get("/api/v1/billing/balance-summary", headers=admin).status_code == 200
    receipts = client.get("/api/v1/billing/receipts", headers=admin).json()
    assert len(receipts) == 2  # aktivasi + renewal


def test_menunggak_lewat_batas_dibatalkan_dan_subscribe_baru(client, billing_env, monkeypatch):  # noqa: F811
    """#44 menunggak > PAST_DUE_CANCEL_DAYS -> dibatalkan; subscribe baru
    membatalkan baris menunggak (G11) sehingga hanya satu langganan berlaku."""
    from app.modules.billing.service import now_utc

    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", True)
    admin, tenant_id = _paid_tenant(client)

    def _past_due(days: int):
        def _apply(db):
            from app.modules.billing.service import current_subscription

            sub = current_subscription(db, UUID(tenant_id))
            sub.status = sub.status.__class__("menunggak")
            sub.past_due_since = now_utc() - timedelta(days=days)
            db.commit()

        run_in_tenant(client, tenant_id, _apply)

    _past_due(5)
    resp = client.post("/api/v1/billing/subscribe", headers=admin, json={"tier": "tier2"})
    assert resp.status_code == 200, resp.text
    webhook(client, {"id": resp.json()["checkout_url"].split("/")[3], "status": "PAID"})
    statuses = [s.status.value for s in _sub(client, tenant_id)]
    assert statuses.count("aktif") == 1 and "menunggak" not in statuses

    _past_due(31)
    assert _run_renewals(client)["actions"].get("cancelled_past_due") == 1
    assert _sub(client, tenant_id)[-1].status.value == "dibatalkan"


def test_auto_renew_mati_dibatalkan_tanpa_charge(client, billing_env, monkeypatch):  # noqa: F811
    """#45"""
    from app.core.payment import sandbox

    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", True)
    admin, tenant_id = _paid_tenant(client)
    add_card(client, admin)
    resp = client.patch("/api/v1/billing/subscription", headers=admin, json={"auto_renew": False})
    assert resp.status_code == 200 and resp.json()["auto_renew"] is False
    set_period_end(client, tenant_id, -1)
    calls_before = len(sandbox.CHARGE_CALLS)
    assert _run_renewals(client)["actions"].get("cancelled_no_renew") == 1
    assert len(sandbox.CHARGE_CALLS) == calls_before
    assert _sub(client, tenant_id)[-1].status.value == "dibatalkan"


def test_guard_tanpa_cron_mengunci_tanpa_http(client, billing_env, monkeypatch):  # noqa: F811
    """#46 tanggal lewat + toleransi -> guard menolak walau cron tidak jalan,
    tanpa panggilan gateway dari guard."""
    from app.modules.billing import payment_service

    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", True)
    admin, tenant_id = _paid_tenant(client)
    set_period_end(client, tenant_id, -1)  # masih dalam toleransi proses 1 hari
    assert client.get("/api/v1/billing/balance-summary", headers=admin).status_code == 200
    set_period_end(client, tenant_id, -3)

    def _no_gateway():
        raise AssertionError("guard tidak boleh memanggil gateway")

    monkeypatch.setattr(payment_service, "get_adapter", _no_gateway)
    resp = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert resp.status_code == 403
    assert resp.headers.get("X-Error-Code") == "subscription_past_due"
    assert _sub(client, tenant_id)[-1].status.value == "menunggak"


def test_metered_blocked_tidak_memblokir_non_metered(client, billing_env):  # noqa: F811
    """#47"""
    admin, tenant_id = _paid_tenant(client)
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)
    assert client.get("/api/v1/billing/transactions", headers=admin).status_code == 200
    summary = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert summary.status_code == 200 and summary.json()["state"] == "empty"
    status = client.get("/api/v1/billing/status", headers=admin).json()
    assert status["access"] == "metered_blocked"


def test_cycle_close_tidak_membuka_siklus_di_luar_masa_bayar(client, billing_env, monkeypatch):  # noqa: F811
    """#48"""
    from app.modules.billing.cycle_close import close_cycle_for_tenant
    from app.modules.billing.service import _get_open_cycle

    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", True)
    _, tenant_id = _paid_tenant(client)
    set_period_end(client, tenant_id, -1)

    def _apply(db):
        cycle = _get_open_cycle(db, UUID(tenant_id))
        cycle.period_start = date.today() - timedelta(days=31)
        cycle.period_end = date.today() - timedelta(days=1)
        db.commit()
        return close_cycle_for_tenant(db, UUID(tenant_id))

    assert run_in_tenant(client, tenant_id, _apply) is None
    monkeypatch.setattr(billing_env, "billing_renewal_enforcement", False)
    assert run_in_tenant(client, tenant_id, _apply) is not None
