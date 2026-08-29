"""Test multi-tenant: provisioning platform, isolasi data, dan pembatasan akses."""

from tests.conftest import _auth_header, _login_header, _platform_admin_header


def _provision(client, slug: str, name: str | None = None) -> dict:
    plat = _platform_admin_header(client)
    resp = client.post(
        "/api/v1/platform/tenants",
        headers=plat,
        json={
            "name": name or f"Tenant {slug}",
            "slug": slug,
            "admin_email": f"admin-{slug}@example.com",
            "admin_password": "password123",
            "admin_full_name": f"Admin {slug}",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # Tenant provisioning baru mulai tanpa lisensi (Fase 7). Untuk keperluan
    # pengujian isolasi data, aktifkan semua aplikasi lewat platform.
    apps = client.get(f"/api/v1/platform/tenants/{body['id']}/licenses", headers=plat).json()
    for lic in apps:
        set_resp = client.patch(
            f"/api/v1/platform/tenants/{body['id']}/licenses/{lic['app_key']}",
            headers=plat,
            json={"status": "aktif"},
        )
        assert set_resp.status_code == 200, set_resp.text
    return body


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
    # termasuk agregat dashboard lintas-tenant
    resp = client.get("/api/v1/overview", headers=plat)
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

    created = client.post("/api/v1/clients", headers=alpha, json={"name": "Klien Milik Alpha"})
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
        ok.json()["tenant_id"] == client.get("/api/v1/auth/me", headers=alpha).json()["tenant_id"]
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


def test_billing_mode_override_per_tenant(client):
    """PRD v3.0 §1 — mode operasi per-tenant override (PlatformTenants.tsx).

    Regresi untuk bug audit.log_event(target_type=/target_id=/payload=) yang
    membuat endpoint ini pernah gagal diam-diam sebelum diperbaiki.
    """
    body = _provision(client, "delta")
    plat = _platform_admin_header(client)

    listed = client.get("/api/v1/platform/tenants", headers=plat).json()
    seeded = next(t for t in listed if t["id"] == body["id"])
    assert seeded["billing_mode"] == "inherit"

    to_internal = client.patch(
        f"/api/v1/platform/tenants/{body['id']}/billing-mode",
        headers=plat,
        json={"billing_mode": "internal"},
    )
    assert to_internal.status_code == 200, to_internal.text
    assert to_internal.json()["billing_mode"] == "internal"

    to_commercial = client.patch(
        f"/api/v1/platform/tenants/{body['id']}/billing-mode",
        headers=plat,
        json={"billing_mode": "commercial"},
    )
    assert to_commercial.status_code == 200
    assert to_commercial.json()["billing_mode"] == "commercial"

    invalid = client.patch(
        f"/api/v1/platform/tenants/{body['id']}/billing-mode",
        headers=plat,
        json={"billing_mode": "gratis"},
    )
    assert invalid.status_code == 422


def test_tenant_usage_report(client):
    """PRD v3.0 §2 — laporan estimasi pemakaian & tagihan (read-only)."""
    from tests.test_finance import _seed_client_with_payroll

    body = _provision(client, "epsilon")
    plat = _platform_admin_header(client)
    headers = _login(client, "admin-epsilon@example.com")
    tenant_id = body["id"]

    # Talent: satu kandidat aktif (belum arsip, belum ada CvIntake → dihitung aktif)
    client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Kandidat Usage"}
    )

    # Workforce + Revenue: seed klien → JO → placement → onboard → payrol → invoice
    client_id, _ = _seed_client_with_payroll(client, headers, name="PT Usage Report")
    jo_id = client.get("/api/v1/recruitment/job-orders", headers=headers).json()[0]["id"]

    # Match execution (billable) untuk JO tersebut
    matched = client.post(
        f"/api/v1/recruitment/job-orders/{jo_id}/match", headers=headers, json={"top_k": 5}
    )
    assert matched.status_code == 200, matched.text

    invoice = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 200_000},
    ).json()
    tax_set = client.put(
        f"/api/v1/finance/invoices/{invoice['id']}/tax-invoice",
        headers=headers,
        json={
            "lawan_npwp": "01.234.567.8-901.000",
            "lawan_nama": "PT Usage Report",
            "dpp_amount": 200_000,
            "kode_transaksi": "01",
            "no_seri_faktur": "010.001-26.00000123",
        },
    )
    assert tax_set.status_code == 200, tax_set.text
    tax_sent = client.post(
        f"/api/v1/finance/invoices/{invoice['id']}/tax-invoice/send", headers=headers
    )
    assert tax_sent.status_code == 200, tax_sent.text

    # talent/employee aktif = snapshot saat ini; match execution, invoice
    # (issued_date), dan faktur sent semuanya tercatat "sekarang" (waktu
    # jalan test) — pakai periode berjalan (default), bukan periode nominal
    # payrol (year=2026,month=6) yang dipakai _seed_client_with_payroll.
    report_now = client.get(f"/api/v1/platform/tenants/{tenant_id}/usage", headers=plat)
    assert report_now.status_code == 200, report_now.text
    now_data = report_now.json()
    by_sku_now = {(line["sku"], line["metric"]): line for line in now_data["lines"]}

    # 2 kandidat: satu dibuat langsung, satu lagi via _seed_client_with_payroll
    talent = by_sku_now[("talent", "talent aktif")]
    assert talent["qty"] == 2
    assert talent["amount"] == 2 * 15_000

    match_line = by_sku_now[("talent", "match execution")]
    assert match_line["qty"] == 1
    assert match_line["amount"] == 2_000

    workforce = by_sku_now[("workforce", "employee aktif")]
    assert workforce["qty"] == 1
    assert workforce["amount"] == 10_000

    revenue = by_sku_now[("revenue", "invoice+faktur")]
    assert revenue["qty_invoice"] == 1
    assert revenue["qty_faktur"] == 1
    assert revenue["amount"] == 1 * 5_000 + 1 * 8_000 + 1_000_000

    govern = by_sku_now[("govern", "flat")]
    assert govern["amount"] is None

    ai_addon = by_sku_now[("ai_addon", "token")]
    assert ai_addon["amount"] is None

    assert now_data["total_known"] == sum(
        line["amount"] for line in now_data["lines"] if line["amount"] is not None
    )

    # Cabut lisensi Talent Cloud → baris talent hilang sepenuhnya (bukan qty=0)
    for key in ("sales_crm", "recruitment"):
        revoke = client.patch(
            f"/api/v1/platform/tenants/{tenant_id}/licenses/{key}",
            headers=plat,
            json={"status": "kedaluwarsa"},
        )
        assert revoke.status_code == 200, revoke.text
    after_revoke = client.get(
        f"/api/v1/platform/tenants/{tenant_id}/usage",
        headers=plat,
        params={"period": "2026-06"},
    ).json()
    assert not any(line["sku"] == "talent" for line in after_revoke["lines"])

    bad_period = client.get(
        f"/api/v1/platform/tenants/{tenant_id}/usage",
        headers=plat,
        params={"period": "not-a-period"},
    )
    assert bad_period.status_code == 422
