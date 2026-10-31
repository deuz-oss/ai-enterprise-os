"""Fase 28 lanjutan: auto-reload sungguhan & blokir metered (rencana §13
kasus 10-22). Sandbox adapter (token ajaib) -- tanpa kredensial asli."""

from datetime import timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from tests.billing_support import (  # noqa: F401 - fixture
    add_card,
    billing_env,
    enable_auto_reload,
    run_in_tenant,
    set_balances,
    setup_tenant,
    webhook,
)
from tests.conftest import _platform_admin_header


def _debit(client, tenant_id: str, amount: float) -> None:
    from app.modules.billing.service import record_credit_transaction

    def _apply(db):
        record_credit_transaction(db, amount=-amount, ref_event="test.debit", allow_negative=True)
        db.commit()

    run_in_tenant(client, tenant_id, _apply)


def _charges(client, tenant_id: str):
    from app.modules.billing.models import PaymentCharge

    return run_in_tenant(
        client,
        tenant_id,
        lambda db: list(
            db.execute(select(PaymentCharge).order_by(PaymentCharge.created_at)).scalars()
        ),
    )


def _account(client, tenant_id: str):
    from app.modules.billing.service import _get_or_create_credit_account

    return run_in_tenant(
        client, tenant_id, lambda db: _get_or_create_credit_account(db, UUID(tenant_id))
    )


def _reload_rows(client, tenant_id: str):
    from app.modules.billing.models import CreditTransaction, CreditTransactionType

    return run_in_tenant(
        client,
        tenant_id,
        lambda db: list(
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.type == CreditTransactionType.topup_auto_reload
                )
            ).scalars()
        ),
    )


def _run_cron(client):
    plat = _platform_admin_header(client)
    resp = client.post("/api/v1/platform/internal/run-auto-reload", headers=plat)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _prepare(client, token: str = "sbx-tok-ok", threshold: float = 50_000):
    admin, tenant_id = setup_tenant(client)
    add_card(client, admin, token)
    enable_auto_reload(client, admin, threshold)
    set_balances(client, tenant_id, cycle_remaining=60_000, credit=0)
    return admin, tenant_id


def test_debit_di_bawah_ambang_membuat_charge_pending(client, billing_env):  # noqa: F811
    """#10 + #11 satu charge pending + kunci in-flight; debit kedua tidak
    menambah charge (compare-and-set)."""
    _, tenant_id = _prepare(client)
    _debit(client, tenant_id, 20_000)
    charges = _charges(client, tenant_id)
    assert len(charges) == 1
    assert charges[0].status.value == "pending"
    assert charges[0].purpose.value == "auto_reload"
    assert _account(client, tenant_id).auto_reload_in_flight_charge_id == charges[0].id
    _debit(client, tenant_id, 5_000)
    assert len(_charges(client, tenant_id)) == 1


def test_cron_mengeksekusi_charge_sukses(client, billing_env):  # noqa: F811
    """#12 ledger topup_auto_reload +100rb, kwitansi terbit, kunci dilepas."""
    _, tenant_id = _prepare(client)
    _debit(client, tenant_id, 20_000)
    _run_cron(client)
    rows = _reload_rows(client, tenant_id)
    assert len(rows) == 1 and float(rows[0].amount) == 100_000
    assert rows[0].receipt_id is not None
    account = _account(client, tenant_id)
    assert account.auto_reload_in_flight_charge_id is None
    assert account.auto_reload_failure_count == 0
    assert float(account.balance) == 100_000
    assert _charges(client, tenant_id)[0].status.value == "succeeded"


def test_jalur_reaktif_sukses(client, billing_env):  # noqa: F811
    """#13 saldo 0 -> assert_metered_allowed menjalankan auto-reload sinkron,
    debit metered berikutnya berhasil (bukan 402)."""
    from app.modules.billing.service import assert_metered_allowed, charge_metered_event

    _, tenant_id = _prepare(client)
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)

    def _apply(db):
        assert_metered_allowed(db, 2_000)
        rows = charge_metered_event(db, amount=2_000, ref_event="test.metered")
        db.commit()
        return rows

    rows = run_in_tenant(client, tenant_id, _apply)
    assert rows and rows[0].type.value == "debit_credit"
    assert len(_reload_rows(client, tenant_id)) == 1
    assert float(_account(client, tenant_id).balance) == 98_000


def test_jalur_reaktif_gagal_memblokir_metered(client, billing_env):  # noqa: F811
    """#14 charge ditolak -> 402 metered_blocked, metered_blocked_at terisi,
    jadwal retry +15 menit."""
    from app.modules.billing.service import as_aware, assert_metered_allowed, now_utc

    _, tenant_id = _prepare(client, "sbx-tok-decline")
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)
    with pytest.raises(HTTPException) as exc:
        run_in_tenant(client, tenant_id, lambda db: assert_metered_allowed(db, 2_000))
    assert exc.value.status_code == 402
    assert (exc.value.headers or {}).get("X-Error-Code") == "metered_blocked"
    account = _account(client, tenant_id)
    assert account.metered_blocked_at is not None
    assert account.metered_block_reason == "auto_reload_failed"
    assert account.auto_reload_failure_count == 1
    assert account.auto_reload_last_error == "CARD_DECLINED"
    delta = as_aware(account.auto_reload_next_attempt_at) - now_utc()
    assert timedelta(minutes=14) < delta <= timedelta(minutes=15)


def test_backoff_lalu_berhenti(client, billing_env):  # noqa: F811
    """Kebijakan retry K6: +15m, +1j, +6j, lalu berhenti otomatis."""
    from app.modules.billing.auto_reload import BACKOFF, MAX_FAILURES, on_charge_failure

    _, tenant_id = _prepare(client, "sbx-tok-decline")
    _debit(client, tenant_id, 20_000)
    charge = _charges(client, tenant_id)[0]

    def _fail(db):
        from app.modules.billing.models import PaymentCharge

        c = db.get(PaymentCharge, charge.id)
        on_charge_failure(db, c, "CARD_DECLINED")
        db.commit()

    for _ in range(MAX_FAILURES):
        run_in_tenant(client, tenant_id, _fail)
    account = _account(client, tenant_id)
    assert account.auto_reload_failure_count == MAX_FAILURES == len(BACKOFF) + 1
    assert account.auto_reload_next_attempt_at is None
    # Berhenti: debit berikutnya tidak memicu charge baru.
    _debit(client, tenant_id, 1_000)
    assert len(_charges(client, tenant_id)) == 1


def test_timeout_direkonsiliasi_tanpa_charge_ganda(client, billing_env):  # noqa: F811
    """#15 timeout -> unknown; cron berikutnya get_charge_by_reference dulu,
    tidak ada panggilan charge kedua (key sama, tidak pernah key baru)."""
    from app.core.payment import sandbox

    _, tenant_id = _prepare(client, "sbx-tok-timeout")
    _debit(client, tenant_id, 20_000)
    _run_cron(client)
    charge = _charges(client, tenant_id)[0]
    assert charge.status.value == "unknown"
    assert sandbox.CHARGE_CALLS.count(charge.idempotency_key) == 1

    def _due(db):
        from app.modules.billing.models import PaymentCharge
        from app.modules.billing.service import now_utc

        db.get(PaymentCharge, charge.id).next_retry_at = now_utc() - timedelta(minutes=1)
        db.commit()

    run_in_tenant(client, tenant_id, _due)
    _run_cron(client)
    assert _charges(client, tenant_id)[0].status.value == "succeeded"
    assert sandbox.CHARGE_CALLS.count(charge.idempotency_key) == 1
    assert len(_reload_rows(client, tenant_id)) == 1


def test_idempotensi_charge_dan_sukses_ganda(client, billing_env):  # noqa: F811
    """#16 kirim ulang key sama -> hasil sama; sukses diterapkan dua kali
    -> satu kredit saja."""
    from app.core.payment.sandbox import SandboxPaymentAdapter
    from app.modules.billing import charges as charges_mod

    adapter = SandboxPaymentAdapter()
    first = adapter.charge_saved_method(
        provider_payment_method_id="sbx-pm-ok-abc123abc123",
        customer_id=None,
        amount=100_000,  # type: ignore[arg-type]
        reference_id="idem-test-1",
        idempotency_key="idem-test-1",
        description="x",
    )
    second = adapter.charge_saved_method(
        provider_payment_method_id="sbx-pm-ok-abc123abc123",
        customer_id=None,
        amount=100_000,  # type: ignore[arg-type]
        reference_id="idem-test-1",
        idempotency_key="idem-test-1",
        description="x",
    )
    assert first == second

    _, tenant_id = _prepare(client)
    _debit(client, tenant_id, 20_000)
    charge = _charges(client, tenant_id)[0]

    def _succeed(db):
        from app.modules.billing.models import PaymentCharge

        c = db.get(PaymentCharge, charge.id)
        return charges_mod.apply_charge_success(db, c, provider_charge_id="pr-1")

    assert run_in_tenant(client, tenant_id, _succeed) is True
    assert run_in_tenant(client, tenant_id, _succeed) is False
    assert len(_reload_rows(client, tenant_id)) == 1


def test_webhook_setelah_sukses_tidak_kredit_dobel(client, billing_env):  # noqa: F811
    """#17 charge pending -> webhook sukses (sandbox) -> kredit; webhook
    payment.succeeded kedua (dedup key beda) -> ignored, kredit tetap satu."""
    admin, tenant_id = _prepare(client, "sbx-tok-pending")
    _debit(client, tenant_id, 20_000)
    _run_cron(client)
    charge = _charges(client, tenant_id)[0]
    assert charge.status.value == "processing"
    resp = client.post(f"/api/v1/billing/sandbox/charges/{charge.id}/succeed", headers=admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    again = webhook(
        client,
        {
            "event": "payment.succeeded",
            "data": {
                "payment_request_id": "pr-x",
                "reference_id": charge.idempotency_key,
                "status": "SUCCEEDED",
            },
        },
        headers={"webhook-id": "evt-lain-123"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "ignored"
    assert len(_reload_rows(client, tenant_id)) == 1


def test_topup_manual_mencabut_blokir(client, billing_env):  # noqa: F811
    """#18 setelah diblokir, top-up invoice sukses mencabut blokir."""
    from app.modules.billing.service import assert_metered_allowed

    admin, tenant_id = _prepare(client, "sbx-tok-decline")
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)
    with pytest.raises(HTTPException):
        run_in_tenant(client, tenant_id, lambda db: assert_metered_allowed(db, 2_000))
    topup = client.post("/api/v1/billing/topup", headers=admin, json={"amount": 50_000})
    assert topup.status_code == 200, topup.text
    invoice_id = topup.json()["checkout_url"].split("/")[3]
    paid = client.post(f"/api/v1/billing/sandbox/invoices/{invoice_id}/pay", headers=admin)
    assert paid.status_code == 200, paid.text
    account = _account(client, tenant_id)
    assert account.metered_blocked_at is None
    run_in_tenant(client, tenant_id, lambda db: assert_metered_allowed(db, 2_000))


def test_ai_diblokir_sebelum_http(client, billing_env, monkeypatch):  # noqa: F811
    """#19 chat_completion saat saldo habis -> 402 sebelum HTTP ke LLM."""
    import httpx
    from app.core import llm
    from app.core.config import get_settings
    from app.core.tenancy import set_tenant

    _, tenant_id = setup_tenant(client)
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)
    monkeypatch.setattr(get_settings(), "ai_base_url", "http://llm.test/v1")

    def _boom(*args, **kwargs):
        raise AssertionError("HTTP ke provider LLM tidak boleh terjadi")

    monkeypatch.setattr(httpx, "post", _boom)
    set_tenant(UUID(tenant_id))
    try:
        with pytest.raises(HTTPException) as exc:
            llm.chat_completion("s", "u", feature="recruitment.match_explain")
        assert exc.value.status_code == 402
        # Pengecualian K7: pipeline AI Interview yang sedang berjalan tidak diblokir.
        with pytest.raises(AssertionError):
            llm.chat_completion("s", "u", feature="ai_interview.scoring")
    finally:
        set_tenant(None)


def test_tenant_bypass_tidak_pernah_diblokir(client, billing_env):  # noqa: F811
    """#20 tenant billing internal: tidak ada auto-reload, tidak pernah 402."""
    from app.modules.billing.service import assert_metered_allowed

    from tests.conftest import _platform_admin_header as plat_header

    admin, tenant_id = _prepare(client)
    set_balances(client, tenant_id, cycle_remaining=0, credit=0)
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/billing-mode",
        headers=plat_header(client),
        json={"billing_mode": "internal"},
    )
    run_in_tenant(client, tenant_id, lambda db: assert_metered_allowed(db, 2_000))
    _debit(client, tenant_id, 20_000)
    assert _charges(client, tenant_id) == []
    status = client.get("/api/v1/billing/status", headers=admin).json()
    assert status["access"] == "full"


def test_effective_false_saat_pm_kedaluwarsa(client, billing_env):  # noqa: F811
    """#21 PM default kedaluwarsa (webhook) -> effective=false."""
    admin, tenant_id = _prepare(client)
    pm_id = client.get("/api/v1/billing/payment-methods", headers=admin).json()[0]["id"]

    def _ref(db):
        from app.modules.billing.models import TenantPaymentMethod

        return db.get(TenantPaymentMethod, UUID(pm_id)).reference_id

    reference = run_in_tenant(client, tenant_id, _ref)
    resp = webhook(
        client,
        {
            "event": "payment_method.expired",
            "data": {"id": "sbx-pm", "reference_id": reference, "status": "EXPIRED"},
        },
    )
    assert resp.status_code == 200 and resp.json()["status"] == "ok", resp.text
    settings_now = client.get("/api/v1/billing/auto-reload-settings", headers=admin).json()
    assert settings_now["effective"] is False
    assert settings_now["reason"] == "no_payment_method"


def test_tanpa_batas_bulanan(client, billing_env):  # noqa: F811
    """#22 lima siklus pemicu-sukses berturut-turut semuanya tereksekusi."""
    _, tenant_id = _prepare(client)
    set_balances(client, tenant_id, cycle_remaining=0, credit=40_000)
    for _ in range(5):
        _run_cron(client)
        _debit(client, tenant_id, 100_000)
    assert len(_reload_rows(client, tenant_id)) == 5
