"""Fase 28 lanjutan: idempotensi webhook (rencana §13 kasus 23-28)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select

from tests.billing_support import (  # noqa: F401 - fixture
    billing_env,
    run_in_tenant,
    setup_tenant,
    webhook,
)


def _topup_intent(client, admin) -> str:
    resp = client.post("/api/v1/billing/topup", headers=admin, json={"amount": 75_000})
    assert resp.status_code == 200, resp.text
    return resp.json()["checkout_url"].split("/")[3]


def _event_count(client) -> int:
    from app.modules.billing.models import PaymentWebhookEvent

    db = client.testing_session()
    try:
        return db.scalar(select(func.count(PaymentWebhookEvent.id))) or 0
    finally:
        db.close()


def _topups(client, tenant_id: str) -> int:
    from app.modules.billing.models import CreditTransaction, CreditTransactionType

    return run_in_tenant(
        client,
        tenant_id,
        lambda db: db.scalar(
            select(func.count(CreditTransaction.id)).where(
                CreditTransaction.type == CreditTransactionType.topup_manual
            )
        ),
    )


def test_token_salah_tanpa_baris_event(client, billing_env):  # noqa: F811
    """#23"""
    before = _event_count(client)
    resp = client.post(
        "/api/v1/billing/webhook/xendit",
        headers={"X-Callback-Token": "salah"},
        json={"id": "x", "status": "PAID"},
    )
    assert resp.status_code == 401
    assert _event_count(client) == before


def test_event_duplikat_efek_tunggal(client, billing_env):  # noqa: F811
    """#24"""
    admin, tenant_id = setup_tenant(client)
    invoice_id = _topup_intent(client, admin)
    payload = {"id": invoice_id, "external_id": "aeos-topup-x", "status": "PAID"}
    first = webhook(client, payload)
    assert first.status_code == 200 and first.json()["status"] == "ok", first.text
    second = webhook(client, payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert _topups(client, tenant_id) == 1


def test_race_reconcile_hanya_satu_pemenang(client, billing_env):  # noqa: F811
    """#25 perbaikan G7: dua sesi mengklaim intent yang sama -> satu menang."""
    from app.modules.billing.payment_service import _claim_intent, find_intent

    admin, _ = setup_tenant(client)
    invoice_id = _topup_intent(client, admin)
    s1, s2 = client.testing_session(), client.testing_session()
    try:
        i1, i2 = find_intent(s1, invoice_id), find_intent(s2, invoice_id)
        assert i1 is not None and i2 is not None
        now = datetime.now(UTC)
        won1 = _claim_intent(s1, i1.id, now)
        s1.commit()
        won2 = _claim_intent(s2, i2.id, now)
        s2.commit()
        assert [won1, won2] == [True, False]
    finally:
        s1.close()
        s2.close()


def test_status_terminal_tidak_ditimpa(client, billing_env):  # noqa: F811
    """#26 EXPIRED setelah PAID diabaikan; payment.failed setelah succeeded
    diabaikan (lihat juga test_billing_auto_reload)."""
    from app.modules.billing.models import PaymentIntent

    admin, tenant_id = setup_tenant(client)
    invoice_id = _topup_intent(client, admin)
    webhook(client, {"id": invoice_id, "status": "PAID"})
    late = webhook(client, {"id": invoice_id, "status": "EXPIRED"})
    assert late.status_code == 200 and late.json()["status"] == "ignored"
    status = run_in_tenant(
        client,
        tenant_id,
        lambda db: db.execute(
            select(PaymentIntent.status).where(PaymentIntent.provider_invoice_id == invoice_id)
        ).scalar_one(),
    )
    assert status.value == "paid"


def test_exception_handler_500_lalu_retry_sukses(client, billing_env, monkeypatch):  # noqa: F811
    """#27 exception -> 500, event failed, tanpa efek parsial; kirim ulang
    (event failed) diproses sukses."""
    from app.modules.billing import payment_service

    admin, tenant_id = setup_tenant(client)
    invoice_id = _topup_intent(client, admin)
    original = payment_service._apply_intent_effect

    def _boom(*args, **kwargs):
        raise RuntimeError("gangguan sementara")

    monkeypatch.setattr(payment_service, "_apply_intent_effect", _boom)
    failed = webhook(client, {"id": invoice_id, "status": "PAID"})
    assert failed.status_code == 500
    assert _topups(client, tenant_id) == 0

    monkeypatch.setattr(payment_service, "_apply_intent_effect", original)
    retried = webhook(client, {"id": invoice_id, "status": "PAID"})
    assert retried.status_code == 200 and retried.json()["status"] == "ok", retried.text
    assert _topups(client, tenant_id) == 1


def test_reference_tenant_tidak_dikenal_diabaikan(client, billing_env):  # noqa: F811
    """#28"""
    setup_tenant(client)
    resp = webhook(
        client,
        {
            "event": "payment.succeeded",
            "data": {
                "payment_request_id": "pr-zzz",
                "reference_id": f"aeos-ar-{UUID(int=7)}-abc",
                "status": "SUCCEEDED",
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    resp2 = webhook(client, {"event": "payment.succeeded", "data": {"reference_id": "acak"}})
    assert resp2.status_code == 200 and resp2.json()["status"] == "ignored"
