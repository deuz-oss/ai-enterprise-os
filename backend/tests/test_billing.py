"""Fase 28: ledger kredit Opsi G -- record_credit_transaction, cascade
cycle->saldo, fail-closed aksi bertarif, dan penutupan cycle periodik."""

from datetime import date, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException

from tests.conftest import _auth_header, _platform_admin_header


def _default_tenant_id(client) -> str:
    plat = _platform_admin_header(client)
    tenants = client.get("/api/v1/platform/tenants", headers=plat).json()
    return next(t["id"] for t in tenants if t["slug"] == "default")


def _set_commercial(client, tenant_id: str) -> None:
    plat = _platform_admin_header(client)
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )


def _seed_subscription_and_cycle(
    client, tenant_id: str, *, cycle_included: float = 10_000, cycle_days_ago_start: int = 0
):
    """Seed TenantSubscription aktif + satu TenantBudgetCycle terbuka."""
    from app.core.tenancy import set_tenant
    from app.modules.billing.models import (
        SubscriptionStatus,
        SubscriptionTier,
        TenantBudgetCycle,
        TenantSubscription,
    )

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        sub = TenantSubscription(
            tenant_id=tid,
            tier=SubscriptionTier.tier1,
            monthly_fee=500_000,
            included_budget=500_000,
            status=SubscriptionStatus.active,
        )
        db.add(sub)
        db.flush()
        start = date.today() - timedelta(days=cycle_days_ago_start)
        cycle = TenantBudgetCycle(
            tenant_id=tid,
            subscription_id=sub.id,
            period_start=start,
            period_end=start + timedelta(days=30),
            included_budget=cycle_included,
            consumed=0,
        )
        db.add(cycle)
        db.commit()
        db.refresh(sub)
        db.refresh(cycle)
        return sub, cycle
    finally:
        set_tenant(None)
        db.close()


def test_record_credit_transaction_debits_cycle_then_credit_account(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.models import CreditTransactionType
    from app.modules.billing.service import (
        _get_or_create_credit_account,
        record_credit_transaction,
    )

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=5_000)

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        account = _get_or_create_credit_account(db, tid)
        account.balance = 10_000
        db.commit()

        # Debit kecil, cukup dari cycle saja.
        rows = record_credit_transaction(db, amount=-2_000, ref_event="test.small")
        db.commit()
        assert len(rows) == 1
        assert rows[0].type == CreditTransactionType.debit_cycle
        assert float(rows[0].amount) == -2_000

        # Debit yang melintasi cycle (sisa 3rb) + saldo top-up -> 2 baris.
        rows2 = record_credit_transaction(db, amount=-5_000, ref_event="test.spanning")
        db.commit()
        assert len(rows2) == 2
        assert rows2[0].type == CreditTransactionType.debit_cycle
        assert float(rows2[0].amount) == -3_000
        assert rows2[1].type == CreditTransactionType.debit_credit
        assert float(rows2[1].amount) == -2_000

        account = _get_or_create_credit_account(db, tid)
        assert float(account.balance) == 8_000  # 10rb - 2rb dari debit kedua
    finally:
        set_tenant(None)
        db.close()


def test_insufficient_credit_raises_and_allow_negative_bypasses(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.service import (
        InsufficientCreditError,
        _get_or_create_credit_account,
        record_credit_transaction,
    )

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000)

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        account = _get_or_create_credit_account(db, tid)
        account.balance = 500
        db.commit()

        with pytest.raises(InsufficientCreditError):
            record_credit_transaction(db, amount=-5_000, ref_event="test.habis")
        db.rollback()

        # allow_negative=True (cycle-close) tidak pernah menolak.
        rows = record_credit_transaction(
            db, amount=-5_000, ref_event="test.habis.paksa", allow_negative=True
        )
        db.commit()
        assert len(rows) == 2
        account = _get_or_create_credit_account(db, tid)
        assert float(account.balance) < 0
    finally:
        set_tenant(None)
        db.close()


def test_billing_bypass_short_circuits_no_ledger_row(client):
    """Tenant tanpa commercial (default `inherit`, APP_MODE=internal di test)
    -- record_credit_transaction TIDAK boleh menulis apa pun."""
    from app.core.tenancy import set_tenant
    from app.modules.billing.models import CreditTransaction
    from app.modules.billing.service import record_credit_transaction
    from sqlalchemy import select

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    # SENGAJA tidak _set_commercial -- billing_mode tetap "inherit".

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        rows = record_credit_transaction(db, amount=-999, ref_event="test.bypass")
        assert rows == []
        count = db.execute(select(CreditTransaction)).scalars().all()
        assert len(count) == 0
    finally:
        set_tenant(None)
        db.close()


def test_charge_metered_event_translates_to_402(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.service import charge_metered_event

    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=100)

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        with pytest.raises(HTTPException) as exc_info:
            charge_metered_event(db, amount=2_000, ref_event="test.metered")
        assert exc_info.value.status_code == 402
    finally:
        set_tenant(None)
        db.close()


def test_match_candidates_billable_charges_ledger_end_to_end(client):
    """Integrasi lewat API sungguhan: POST /job-orders/{id}/match dengan
    saldo cukup -> ledger bertambah; saldo habis -> 402, audit tidak tercatat."""
    from app.modules.billing.models import CreditTransaction

    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    cid = client.post(
        "/api/v1/clients", headers=admin, json={"name": "PT Klien Uji Billing"}
    ).json()["id"]
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={
            "client_id": cid,
            "title": "Test Billing JO",
            "headcount": 1,
            "salary_min": 4_000_000,
            "salary_max": 5_000_000,
        },
    )
    assert jo.status_code == 201, jo.text
    jo_id = jo.json()["id"]

    resp = client.post(f"/api/v1/recruitment/job-orders/{jo_id}/match", headers=admin)
    assert resp.status_code == 200, resp.text

    from sqlalchemy import select

    db = client.testing_session()
    try:
        txs = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.ref_event == "recruitment.match_executed"
                )
            )
            .scalars()
            .all()
        )
        assert any(float(t.amount) == -2_000 for t in txs)
    finally:
        db.close()

    # Habiskan saldo tenant supaya match berikutnya 402.
    from app.core.tenancy import set_tenant
    from app.modules.billing.service import _get_open_cycle

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        cycle = _get_open_cycle(db, tid)
        cycle.consumed = cycle.included_budget
        db.commit()
    finally:
        set_tenant(None)
        db.close()

    blocked = client.post(f"/api/v1/recruitment/job-orders/{jo_id}/match", headers=admin)
    assert blocked.status_code == 402, blocked.text


def test_invoice_generate_and_tax_invoice_send_charge_ledger(client):
    from app.modules.billing.models import CreditTransaction
    from sqlalchemy import select

    from tests.test_finance import _seed_client_with_payroll

    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    client_id, _run_id = _seed_client_with_payroll(client, admin, name="PT Billing Faktur")
    gen = client.post(
        "/api/v1/finance/invoices/generate",
        headers=admin,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 1_000_000},
    )
    assert gen.status_code == 201, gen.text
    invoice_id = gen.json()["id"]

    client.put(
        f"/api/v1/finance/invoices/{invoice_id}/tax-invoice",
        headers=admin,
        json={
            "lawan_npwp": "01.234.567.8-901.000",
            "lawan_nama": "PT Billing Faktur",
            "dpp_amount": 1_000_000,
            "kode_transaksi": "01",
            "no_seri_faktur": "010.001-26.00000002",
        },
    )
    sent = client.post(f"/api/v1/finance/invoices/{invoice_id}/tax-invoice/send", headers=admin)
    assert sent.status_code == 200, sent.text

    db = client.testing_session()
    try:
        invoice_tx = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.ref_event == "finance.invoice_issued"
                )
            )
            .scalars()
            .all()
        )
        assert any(float(t.amount) == -5_000 for t in invoice_tx)

        faktur_tx = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.ref_event == "invoice.tax_invoice_sent"
                )
            )
            .scalars()
            .all()
        )
        assert any(float(t.amount) == -8_000 for t in faktur_tx)
    finally:
        db.close()


def test_close_cycle_for_tenant_rolls_over_and_charges_snapshot(client):
    """Cycle diseed dengan period_end MASIH di masa depan (supaya membuat
    karyawan lewat API -- yang juga melewati safety-net di
    `require_active_subscription()` -- belum memicu penutupan lebih dulu),
    baru DIMUNDURKAN langsung via DB sebelum memanggil `close_cycle_for_tenant`
    eksplisit -- supaya pemanggilan di test ini yang benar-benar menutupnya,
    bukan keburu ditutup diam-diam oleh safety-net di request sebelumnya."""
    from app.modules.billing.cycle_close import close_cycle_for_tenant
    from app.modules.billing.models import CreditTransaction
    from sqlalchemy import select

    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _old_sub, old_cycle = _seed_subscription_and_cycle(
        client, tenant_id, cycle_included=500_000, cycle_days_ago_start=0
    )

    client.post(
        "/api/v1/employees",
        headers=admin,
        json={"full_name": "Karyawan Uji Cycle"},
    )

    db = client.testing_session()
    try:
        cycle = db.get(type(old_cycle), old_cycle.id)
        cycle.period_end = date.today() - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    db = client.testing_session()
    try:
        new_cycle = close_cycle_for_tenant(db, UUID(tenant_id))
        assert new_cycle is not None
        assert new_cycle.id != old_cycle.id
        refetched_old = db.get(type(old_cycle), old_cycle.id)
        assert refetched_old.closed_at is not None

        emp_charges = (
            db.execute(
                select(CreditTransaction).where(
                    CreditTransaction.ref_event == "cycle_close.employee_active"
                )
            )
            .scalars()
            .all()
        )
        assert len(emp_charges) == 1
        assert float(emp_charges[0].amount) == -10_000
    finally:
        db.close()

    # Idempotent: panggil lagi langsung sesudahnya -> no-op (cycle baru belum lewat waktunya).
    db = client.testing_session()
    try:
        again = close_cycle_for_tenant(db, UUID(tenant_id))
        assert again is None
    finally:
        db.close()


def test_run_cycle_charge_endpoint_closes_due_cycles(client):
    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=500_000, cycle_days_ago_start=40)

    plat = _platform_admin_header(client)
    resp = client.post("/api/v1/platform/internal/run-cycle-charge", headers=plat)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert tenant_id in body["tenant_ids"]


def test_balance_summary_three_states(client):
    from app.core.tenancy import set_tenant
    from app.modules.billing.service import _get_or_create_credit_account

    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    normal = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert normal.status_code == 200, normal.text
    assert normal.json()["state"] == "normal"
    assert normal.json()["cycle_included"] == 1_000_000

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        account = _get_or_create_credit_account(db, tid)
        account.balance = 0
        from app.modules.billing.service import _get_open_cycle

        cycle = _get_open_cycle(db, tid)
        cycle.consumed = 850_000  # sisa 150rb dari 1jt -> 15% <= 20% ambang warning
        db.commit()
    finally:
        set_tenant(None)
        db.close()

    warning = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert warning.json()["state"] == "warning"

    db = client.testing_session()
    try:
        tid = UUID(tenant_id)
        set_tenant(tid)
        cycle = _get_open_cycle(db, tid)
        cycle.consumed = cycle.included_budget
        db.commit()
    finally:
        set_tenant(None)
        db.close()

    empty = client.get("/api/v1/billing/balance-summary", headers=admin)
    assert empty.json()["state"] == "empty"


def test_auto_reload_settings_persist_but_do_not_execute(client):
    """Preferensi auto-reload cuma disimpan (§0 -- tidak ada data/perilaku
    fiktif): endpoint ini TIDAK memicu charge apa pun, cuma baca/tulis 3
    kolom `TenantCreditAccount.auto_reload_*`."""
    admin = _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=1_000_000)

    default = client.get("/api/v1/billing/auto-reload-settings", headers=admin)
    assert default.status_code == 200, default.text
    assert default.json() == {"enabled": False, "threshold": None, "amount": 100_000}

    updated = client.put(
        "/api/v1/billing/auto-reload-settings",
        headers=admin,
        json={"enabled": True, "threshold": 200_000, "amount": 500_000},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"enabled": True, "threshold": 200_000, "amount": 500_000}

    refetched = client.get("/api/v1/billing/auto-reload-settings", headers=admin)
    assert refetched.json() == {"enabled": True, "threshold": 200_000, "amount": 500_000}


def test_platform_billing_summary_and_subscription_override(client):
    """Milestone 8: panel platform-admin -- ringkasan tier+saldo+riwayat,
    dan override tier manual (bypass Xendit, untuk migrasi/support)."""
    _auth_header(client)
    tenant_id = _default_tenant_id(client)
    _set_commercial(client, tenant_id)
    _seed_subscription_and_cycle(client, tenant_id, cycle_included=500_000)

    plat = _platform_admin_header(client)
    summary = client.get(f"/api/v1/platform/tenants/{tenant_id}/billing-summary", headers=plat)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["tier"] == "tier1"
    assert body["subscription_status"] == "aktif"
    assert body["cycle_included"] == 500_000
    assert body["state"] == "normal"

    override = client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=plat,
        json={"tier": "tier3"},
    )
    assert override.status_code == 200, override.text
    assert override.json()["tier"] == "tier3"

    summary2 = client.get(f"/api/v1/platform/tenants/{tenant_id}/billing-summary", headers=plat)
    body2 = summary2.json()
    assert body2["tier"] == "tier3"
    assert body2["cycle_included"] == 5_000_000

    invalid = client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=plat,
        json={"tier": "tier99"},
    )
    assert invalid.status_code == 422
