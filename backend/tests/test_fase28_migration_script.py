"""Fase 28: script migrasi one-shot Opsi F -> Opsi G.

Menguji `migrate_tenant()` langsung (bukan lewat subprocess) supaya bisa
memeriksa isi DB persis dan reuse fixture `client`/session in-memory yang
sama seperti test lain."""

from uuid import UUID

from tests.conftest import _auth_header, _platform_admin_header


def _default_tenant_id(client) -> str:
    plat = _platform_admin_header(client)
    tenants = client.get("/api/v1/platform/tenants", headers=plat).json()
    return next(t["id"] for t in tenants if t["slug"] == "default")


def _provision_fresh_tenant(client, slug: str) -> str:
    """Tenant baru TANPA paket penuh bawaan (beda dari "default" yang
    di-bootstrap dengan semua app terlisensi -- lihat
    test_apps.py::test_default_tenant_gets_full_package)."""
    plat = _platform_admin_header(client)
    resp = client.post(
        "/api/v1/platform/tenants",
        headers=plat,
        json={
            "name": f"Tenant {slug}",
            "slug": slug,
            "admin_email": f"admin-{slug}@example.com",
            "admin_full_name": "Admin",
            "admin_password": "rahasia-123",
        },
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    plat = _platform_admin_header(client)
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )
    return tenant_id


def _grant_license(client, tenant_id: str, app_key: str) -> None:
    plat = _platform_admin_header(client)
    resp = client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/licenses/{app_key}",
        headers=plat,
        json={"status": "aktif"},
    )
    assert resp.status_code == 200, resp.text


def test_migrate_tenant_bypass_skipped(client):
    """Tenant default billing_mode=inherit + APP_MODE=internal (test env) --
    bypass aktif, tidak perlu subscription sama sekali."""
    from scripts.fase28_migrate_opsi_f_to_g import migrate_tenant

    _auth_header(client)
    tenant_id = _default_tenant_id(client)

    db = client.testing_session()
    try:
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, UUID(tenant_id))
        result = migrate_tenant(db, tenant, apply=False)
        assert result.startswith("[BYPASS]")
    finally:
        db.close()


def test_migrate_tenant_foundation_only_skipped(client):
    from scripts.fase28_migrate_opsi_f_to_g import migrate_tenant

    _auth_header(client)
    tenant_id = _provision_fresh_tenant(client, "fase28-foundation")

    db = client.testing_session()
    try:
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, UUID(tenant_id))
        result = migrate_tenant(db, tenant, apply=False)
        assert result.startswith("[FOUNDATION-ONLY]")
    finally:
        db.close()


def test_migrate_tenant_tier_assignment_by_bundle_count(client):
    from scripts.fase28_migrate_opsi_f_to_g import migrate_tenant

    _auth_header(client)
    tenant_id = _provision_fresh_tenant(client, "fase28-tiering")

    # 1 bundle (talent = sales_crm) -> tier1.
    _grant_license(client, tenant_id, "sales_crm")
    db = client.testing_session()
    try:
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, UUID(tenant_id))
        dry = migrate_tenant(db, tenant, apply=False)
        assert "-> tier1" in dry, dry
    finally:
        db.close()

    # Tambah recruitment -- masih bundle "talent" yang sama (sales_crm +
    # recruitment keduanya bundle talent) -> tetap 1 bundle unik, tier1.
    _grant_license(client, tenant_id, "recruitment")
    db = client.testing_session()
    try:
        tenant = db.get(Tenant, UUID(tenant_id))
        dry = migrate_tenant(db, tenant, apply=False)
        assert "-> tier1" in dry, dry
    finally:
        db.close()

    # Tambah people_ops (bundle workforce) -> 2 bundle unik -> tier2.
    _grant_license(client, tenant_id, "people_ops")
    db = client.testing_session()
    try:
        tenant = db.get(Tenant, UUID(tenant_id))
        dry = migrate_tenant(db, tenant, apply=False)
        assert "-> tier2" in dry, dry
    finally:
        db.close()

    # Tambah accounting (bundle govern) -> 3 bundle unik -> tier3, lalu APPLY
    # sungguhan dan verifikasi isi tiga tabel yang dibuat.
    _grant_license(client, tenant_id, "accounting")
    db = client.testing_session()
    try:
        from app.core.tenancy import set_tenant
        from app.modules.billing.models import (
            SubscriptionTier,
            TenantBudgetCycle,
            TenantCreditAccount,
            TenantSubscription,
        )
        from app.modules.platform.models import Tenant
        from sqlalchemy import select

        tenant = db.get(Tenant, UUID(tenant_id))
        dry = migrate_tenant(db, tenant, apply=False)
        assert "-> tier3" in dry, dry

        applied = migrate_tenant(db, tenant, apply=True)
        assert applied.startswith("[APPLIED]")
        assert "-> tier3" in applied

        set_tenant(UUID(tenant_id))
        sub = db.execute(
            select(TenantSubscription).where(TenantSubscription.tenant_id == UUID(tenant_id))
        ).scalar_one()
        assert sub.tier == SubscriptionTier.tier3
        assert float(sub.monthly_fee) == 5_000_000

        cycle = db.execute(
            select(TenantBudgetCycle).where(TenantBudgetCycle.subscription_id == sub.id)
        ).scalar_one()
        assert float(cycle.included_budget) == 5_000_000

        account = db.execute(
            select(TenantCreditAccount).where(TenantCreditAccount.tenant_id == UUID(tenant_id))
        ).scalar_one()
        assert float(account.balance) == 0
        set_tenant(None)
    finally:
        db.close()


def test_migrate_tenant_idempotent_second_run_skips(client):
    from scripts.fase28_migrate_opsi_f_to_g import migrate_tenant

    _auth_header(client)
    tenant_id = _provision_fresh_tenant(client, "fase28-idempotent")
    _grant_license(client, tenant_id, "sales_crm")

    db = client.testing_session()
    try:
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, UUID(tenant_id))
        first = migrate_tenant(db, tenant, apply=True)
        assert first.startswith("[APPLIED]")

        second = migrate_tenant(db, tenant, apply=True)
        assert second.startswith("[SUDAH ADA]")
    finally:
        db.close()
