"""Test multi-tenant: provisioning platform, isolasi data, dan pembatasan akses."""

from tests.conftest import _auth_header, _login_header, _platform_admin_header


def _provision(client, slug: str, name: str | None = None) -> dict:
    resp = client.post(
        "/api/v1/platform/tenants",
        headers=_platform_admin_header(client),
        json={
            "name": name or f"Tenant {slug}",
            "slug": slug,
            "admin_email": f"admin-{slug}@example.com",
            "admin_password": "password123",
            "admin_full_name": f"Admin {slug}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _login(client, email: str, password: str = "password123") -> dict[str, str]:
    return _login_header(client, email, password)


def test_platform_endpoint_butuh_platform_admin(client):
    headers = _auth_header(client)  # admin tenant biasa
    resp = client.get("/api/v1/platform/tenants", headers=headers)
    assert resp.status_code == 403

    # Platform admin sendiri tidak boleh menyentuh endpoint bisnis
    plat = _platform_admin_header(client)
    resp = client.get("/api/v1/clients", headers=plat)
    assert resp.status_code == 403
    resp = client.get("/api/v1/employees", headers=plat)
    assert resp.status_code == 403


def test_provision_tenant_menghasilkan_admin_yang_bisa_login(client):
    body = _provision(client, "alpha")
    assert body["slug"] == "alpha"
    assert body["admin_initial_password"] == "password123"

    # Slug duplikat ditolak
    dup = client.post(
        "/api/v1/platform/tenants",
        headers=_platform_admin_header(client),
        json={
            "name": "Alpha Lagi",
            "slug": "alpha",
            "admin_email": "lain@example.com",
            "admin_password": "password123",
            "admin_full_name": "Lain",
        },
    )
    assert dup.status_code == 409

    headers = _login(client, "admin-alpha@example.com")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["role"] == "admin"
    assert me["tenant_id"] is not None
    assert str(me["tenant_id"]) == body["id"]


def test_isolasi_data_antar_tenant(client):
    """Client milik tenant A tidak terlihat oleh tenant B maupun platform."""
    _provision(client, "alpha")
    _provision(client, "beta")

    alpha = _login(client, "admin-alpha@example.com")
    beta = _login(client, "admin-beta@example.com")

    created = client.post(
        "/api/v1/clients", headers=alpha, json={"name": "Klien Milik Alpha"}
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    # Alpha melihat datanya sendiri
    assert len(client.get("/api/v1/clients", headers=alpha).json()) == 1

    # Beta tidak melihat apa pun dan tidak bisa mengakses by id
    assert client.get("/api/v1/clients", headers=beta).json() == []
    assert client.get(f"/api/v1/clients/{client_id}", headers=beta).status_code == 404
    # Beta bahkan tidak bisa mengubah/menghapusnya
    assert (
        client.patch(
            f"/api/v1/clients/{client_id}", headers=beta, json={"name": "Diretas"}
        ).status_code
        == 404
    )

    # Isolasi juga berlaku untuk modul lain (karyawan) dan agregat dashboard
    assert client.get("/api/v1/employees", headers=beta).json() == []
    overview = client.get("/api/v1/overview", headers=beta).json()
    assert overview["clients"] == 0


def test_email_harus_unik_global_antar_tenant(client):
    _provision(client, "alpha")
    _provision(client, "beta")
    alpha = _login(client, "admin-alpha@example.com")
    beta = _login(client, "admin-beta@example.com")

    ok = client.post(
        "/api/v1/auth/register",
        headers=alpha,
        json={
            "email": "shared-person@example.com",
            "full_name": "Shared",
            "password": "password123",
            "role": "hr",
        },
    )
    assert ok.status_code == 201
    assert (
        ok.json()["tenant_id"]
        == client.get("/api/v1/auth/me", headers=alpha).json()["tenant_id"]
    )

    # Email sama dari tenant berbeda harus ditolak (batasan v1)
    dup = client.post(
        "/api/v1/auth/register",
        headers=beta,
        json={
            "email": "shared-person@example.com",
            "full_name": "Duplikat",
            "password": "password123",
            "role": "hr",
        },
    )
    assert dup.status_code == 409


def test_tenant_ditangguhkan_tidak_bisa_login(client):
    body = _provision(client, "gamma")

    patch = client.patch(
        f"/api/v1/platform/tenants/{body['id']}",
        headers=_platform_admin_header(client),
        json={"status": "ditangguhkan"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "ditangguhkan"

    denied = client.post(
        "/api/v1/auth/login",
        json={"email": "admin-gamma@example.com", "password": "password123"},
    )
    assert denied.status_code == 403
