"""Fase 7: registry aplikasi (masih dipakai untuk pemetaan path->app_key).
Guard akses bisnis sejak Fase 28 memakai `require_active_subscription()`
(TenantSubscription), bukan lagi lisensi per-SKU -- lihat
`test_guard_blocks_without_subscription_and_passes_once_active`."""

from tests.conftest import _auth_header


def _provision_tenant(client, platform_headers, slug: str) -> dict:
    resp = client.post(
        "/api/v1/platform/tenants",
        headers=platform_headers,
        json={
            "name": f"Tenant {slug}",
            "slug": slug,
            "admin_email": f"admin-{slug}@example.com",
            "admin_full_name": "Admin Baru",
            "admin_password": "rahasia-123",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_registry_covers_all_business_prefixes():
    """Setiap prefix bisnis harus terpetakan ke satu aplikasi registry — PRD v3.0 F."""
    from app.core.apps import app_for_path

    pemetaan = {
        "/leads": "sales_crm",
        "/clients/abc/documents": "sales_crm",
        "/recruitment/candidates": "recruitment",
        "/employees": "people_ops",
        "/payroll/runs": "payroll",
        "/me/payslips": "people_ops",
        "/me/notifications": "people_ops",
        "/finance": "finance",
        "/accounting/journals": "accounting",
        "/esign/requests": "people_ops",
        "/ai/contracts/ask": "ai_addon",
    }
    for path, expected in pemetaan.items():
        assert app_for_path(path) == expected, path
    # Kapabilitas gratis tanpa lisensi.
    for free in ("/auth/login", "/overview", "/platform/tenants", "/files/x", "/apps"):
        assert app_for_path(free) is None, free


def test_default_tenant_gets_full_package(client):
    headers = _auth_header(client)
    apps = client.get("/api/v1/apps", headers=headers).json()
    assert len(apps) == 7
    assert all(a["licensed"] and a["status"] == "aktif" for a in apps)


def _seed_active_subscription(client, tenant_id):
    """Insert `TenantSubscription` langsung via DB -- alur nyata (Xendit
    checkout, Milestone 7) belum ada di titik Milestone 2 ini."""
    from uuid import UUID

    from app.modules.billing.models import SubscriptionStatus, SubscriptionTier, TenantSubscription

    db = client.testing_session()
    try:
        db.add(
            TenantSubscription(
                tenant_id=UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
                tier=SubscriptionTier.tier1,
                monthly_fee=500_000,
                included_budget=500_000,
                status=SubscriptionStatus.active,
            )
        )
        db.commit()
    finally:
        db.close()


def test_guard_blocks_without_subscription_and_passes_once_active(client):
    """Fase 28: penegakan sekarang murni `TenantSubscription` aktif per
    tenant -- keadaan `TenantAppLicense` per-SKU (Opsi F, endpoint
    /platform/tenants/*/licenses & /apps tetap ada untuk historis per
    ADR-0007) TIDAK lagi memengaruhi akses rute bisnis sama sekali."""
    admin = _auth_header(client)

    from tests.conftest import _platform_admin_header

    plat = _platform_admin_header(client)
    tenants = client.get("/api/v1/platform/tenants", headers=plat).json()
    default_id = next(t["id"] for t in tenants if t["slug"] == "default")

    # PRD v3.0: set commercial agar guard tidak bypass (APP_MODE internal di test).
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )

    # Granting lisensi Opsi F lama TIDAK lagi cukup -- tanpa TenantSubscription, tetap 403.
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/licenses/sales_crm",
        headers=plat,
        json={"status": "aktif", "expires_at": None},
    )
    blocked = client.get("/api/v1/leads", headers=admin)
    assert blocked.status_code == 403
    assert "berlangganan" in blocked.json()["detail"]

    # App lain (foundation, tanpa guard) tetap berjalan.
    assert client.get("/api/v1/overview", headers=admin).status_code == 200

    # Aktifkan TenantSubscription -> semua rute berguard langganan lolos sekaligus,
    # termasuk yang app_key Opsi F-nya tidak pernah di-grant (mis. recruitment).
    _seed_active_subscription(client, default_id)
    assert client.get("/api/v1/leads", headers=admin).status_code == 200
    assert client.get("/api/v1/clients", headers=admin).status_code == 200
    assert client.get("/api/v1/recruitment/job-orders", headers=admin).status_code == 200

    # Kembalikan billing_mode.
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "inherit"},
    )


def test_new_tenant_tanpa_subscription_diblokir_lalu_pulih(client):
    from uuid import UUID

    from tests.conftest import _platform_admin_header

    plat = _platform_admin_header(client)
    provisioned = _provision_tenant(client, plat, "acme")
    tenant_id = provisioned["id"]
    assert UUID(tenant_id)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin-acme@example.com", "password": "rahasia-123"},
    )
    token = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Tenant baru mulai tanpa TenantSubscription -> 403 di rute berguard.
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )
    blocked = client.get("/api/v1/me/profile", headers=token)
    assert blocked.status_code == 403
    assert "berlangganan" in blocked.json()["detail"]

    # Berlangganan (disimulasikan langsung -- alur checkout Xendit nyata ada di Milestone 7).
    _seed_active_subscription(client, tenant_id)
    profile = client.get("/api/v1/me/profile", headers=token)
    assert profile.status_code == 404  # lolos guard; 404 karena belum ada data karyawan
    assert client.get("/api/v1/leads", headers=token).status_code == 200
