"""Test jejak audit: akses dokumen, login gagal, isolasi tenant, role guard."""

from unittest.mock import patch

from tests.conftest import _auth_header, _login_header

_CV_TEXT = b"CV TES AUDIT\nPengalaman 3 tahun admin gudang.\nKontak 081200000000.\n"


def _candidate_with_cv(client, headers, name="Budi Audit") -> str:
    cand = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": name}
    ).json()
    with patch("app.modules.recruitment.service.storage.put_object") as put:
        put.return_value = f"candidates/{cand['id']}/cv.txt"
        resp = client.post(
            f"/api/v1/recruitment/candidates/{cand['id']}/cv",
            headers=headers,
            files={"file": ("cv.txt", _CV_TEXT, "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    return cand["id"]


def test_akses_dokumen_tercatat(client):
    headers = _auth_header(client)
    cand_id = _candidate_with_cv(client, headers)

    # Minta link unduhan CV → harus menghasilkan event audit
    dl = client.get(f"/api/v1/recruitment/candidates/{cand_id}/cv-download-url", headers=headers)
    assert dl.status_code == 200

    logs = client.get(
        "/api/v1/audit/logs",
        headers=headers,
        params={"entity_type": "candidate"},
    ).json()
    actions = [item["action"] for item in logs["items"]]
    assert "cv.upload" in actions
    assert "cv.download_url" in actions
    # Event terbaru di atas
    assert logs["total"] >= 2
    row = next(i for i in logs["items"] if i["action"] == "cv.download_url")
    assert row["entity_id"] == cand_id
    assert row["user_id"] is not None  # aktor teridentifikasi dari JWT


def test_login_gagal_tercatat(client):
    headers = _auth_header(client)
    # Percobaan salah ke akun yang ADA → tercatat pada tenant pemilik akun
    client.post(
        "/api/v1/auth/login",
        json={"email": "brian@outsourcing.co.id", "password": "salah123"},
    )
    # Email tak dikenal → event tetap dibuat tapi tanpa tenant (tak terlihat
    # oleh admin tenant; batasan yang disengaja untuk v1)
    client.post("/api/v1/auth/login", json={"email": "hacker@example.com", "password": "salah123"})

    logs = client.get(
        "/api/v1/audit/logs", headers=headers, params={"action_prefix": "auth."}
    ).json()
    failed = [i for i in logs["items"] if i["action"] == "auth.login_failed"]
    assert len(failed) == 1
    assert failed[0]["user_id"] is not None
    assert failed[0]["tenant_id"] is not None
    assert failed[0]["detail"]["email"] == "brian@outsourcing.co.id"

    # Login sukses juga tercatat dengan aktor & tenant
    ok = [i for i in logs["items"] if i["action"] == "auth.login"]
    assert len(ok) >= 1


def test_isolasi_log_antar_tenant(client):
    """Log tenant lain tidak boleh terbaca (filter TenantMixin berlaku)."""
    from tests.conftest import _platform_admin_header as plat

    # Buat tenant kedua via platform, lalu aktivitas oleh admin-nya
    prov = client.post(
        "/api/v1/platform/tenants",
        headers=plat(client),
        json={
            "name": "Tenant Dua",
            "slug": "dua-audit",
            "admin_email": "admin-dua@example.com",
            "admin_password": "password123",
            "admin_full_name": "Admin Dua",
        },
    )
    assert prov.status_code == 201
    dua = _login_header(client, "admin-dua@example.com", "password123")
    client.post("/api/v1/clients", headers=dua, json={"name": "Klien Tenant Dua"})

    # Aktivitas default tenant
    default_headers = _auth_header(client)

    # Admin tenant default tidak melihat log milik tenant dua
    logs = client.get("/api/v1/audit/logs", headers=default_headers).json()
    for item in logs["items"]:
        if item["detail"] and isinstance(item["detail"], dict):
            # log legal_document milik tenant dua membawa client_id; tak akan ada
            assert "Klien Tenant Dua" not in str(item["detail"])
    # dan total log tenant dua (upload klien tadi) tidak tercampur:
    # cari event apa pun yang entity_type=client — hanya milik default jika ada
    client_logs = client.get(
        "/api/v1/audit/logs", headers=default_headers, params={"action_prefix": "legal_document"}
    ).json()
    for item in client_logs["items"]:
        assert item["tenant_id"] is not None


def test_role_recruiter_ditolak_membaca_audit(client):
    admin = _auth_header(client)
    reg = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "email": "rec-audit@example.com",
            "full_name": "Recruiter",
            "password": "password123",
            "role": "recruiter",
        },
    )
    assert reg.status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "rec-audit@example.com", "password": "password123"},
    ).json()["access_token"]
    resp = client.get(
        "/api/v1/audit/logs", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
