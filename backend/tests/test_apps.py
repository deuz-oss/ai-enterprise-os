"""Fase 7: registry aplikasi, lisensi per tenant, dan guard 403."""

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


def test_guard_blocks_and_trial_reactivates(client):
    admin = _auth_header(client)

    # Cabut lisensi Sales CRM → endpoint modul sales 403, lainnya tetap lolos.
    revoked = client.patch(
        "/api/v1/platform/tenants/default/licenses/sales_crm",
        headers=admin,
    )
    # PATCH /platform khusus platform_admin → tenant admin memang ditolak.
    assert revoked.status_code == 403

    # Endpoint lisensi hanya lewat platform admin.
    from tests.conftest import _platform_admin_header

    plat = _platform_admin_header(client)
    tenants = client.get("/api/v1/platform/tenants", headers=plat).json()
    default_id = next(t["id"] for t in tenants if t["slug"] == "default")

    # PRD v3.0: set commercial agar guard tidak bypass (APP_MODE internal di test)
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )

    revoke = client.patch(
        f"/api/v1/platform/tenants/{default_id}/licenses/sales_crm",
        headers=plat,
        json={"status": "kedaluwarsa"},
    )
    assert revoke.status_code == 200, revoke.text

    blocked = client.get("/api/v1/leads", headers=admin)
    assert blocked.status_code == 403
    assert "belum aktif" in blocked.json()["detail"]

    clients_list = client.get("/api/v1/clients", headers=admin)
    assert clients_list.status_code == 403

    # App lain di tenant yang sama tetap berjalan.
    assert client.get("/api/v1/overview", headers=admin).status_code == 200

    # Status di /apps ikut berubah; trial tidak bisa dipakai lagi (sudah pernah).
    apps = {a["key"]: a for a in client.get("/api/v1/apps", headers=admin).json()}
    assert apps["sales_crm"]["licensed"] is False
    assert apps["sales_crm"]["status"] == "kedaluwarsa"
    trial_again = client.post("/api/v1/apps/sales_crm/trial", headers=admin)
    assert trial_again.status_code == 409

    # Platform mengaktifkan kembali → akses pulih.
    renewed = client.patch(
        f"/api/v1/platform/tenants/{default_id}/licenses/sales_crm",
        headers=plat,
        json={"status": "aktif", "expires_at": None},
    )
    assert renewed.status_code == 200
    assert client.get("/api/v1/leads", headers=admin).status_code == 200
    # Kembalikan billing_mode
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "inherit"},
    )


def test_trial_flow_on_provisioned_tenant_then_expiry(client):
    from datetime import UTC, datetime, timedelta
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

    # Tenant provisioning baru mulai tanpa lisensi → endpoint app 403
    # (set commercial agar guard tidak bypass di test APP_MODE internal)
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )
    apps = {a["key"]: a for a in client.get("/api/v1/apps", headers=token).json()}
    assert all(not a["licensed"] for a in apps.values())
    blocked = client.get("/api/v1/me/profile", headers=token)
    assert blocked.status_code == 403
    assert "belum aktif" in blocked.json()["detail"]

    # Trial diaktifkan mandiri oleh admin tenant → lisensi jalan (404 karena
    # belum ada data karyawan, bukan lagi 403 lisensi).
    trial = client.post("/api/v1/apps/people_ops/trial", headers=token)
    assert trial.status_code == 200, trial.text
    assert trial.json()["status"] == "trial"
    expires = datetime.fromisoformat(trial.json()["expires_at"])
    if expires.tzinfo is None:  # SQLite menyimpan naive
        expires = expires.replace(tzinfo=UTC)
    assert (expires - datetime.now(UTC)).days >= 13
    profile = client.get("/api/v1/me/profile", headers=token)
    assert profile.status_code == 404

    # Aplikasi lain masih terkunci.
    assert client.get("/api/v1/leads", headers=token).status_code == 403

    # Trial kedua untuk aplikasi yang sama ditolak meski sudah dicabut platform.
    client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/licenses/people_ops",
        headers=plat,
        json={"status": "kedaluwarsa"},
    )
    second = client.post("/api/v1/apps/people_ops/trial", headers=token)
    assert second.status_code == 409

    # Trial yang sudah kedaluwarsa dianggap tidak berlisensi.
    expired = client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/licenses/recruitment",
        headers=plat,
        json={
            "status": "trial",
            "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
    )
    assert expired.status_code == 200
    assert client.get("/api/v1/recruitment/job-orders", headers=token).status_code == 403
