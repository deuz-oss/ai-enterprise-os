"""Lookup baca-saja lintas modul (audit 2026-11-11 Top-20 #1).

Alur tiap role butuh MEMILIH data modul lain (finance memilih klien saat
membuat invoice, recruiter saat membuat job order, HR/operations untuk payroll
proyek). Dulu dropdown itu memanggil `GET /clients` yang 403 untuk mereka --
kosong tanpa pesan. Test ini menjaga: role yang butuh lolos, yang tidak butuh
tetap ditolak, isi respons minimal, dan tidak bocor antar tenant.
"""

import pytest

from tests.conftest import _auth_header, _login_header
from tests.test_clients import _create_client
from tests.test_platform import _provision

PASSWORD = "rahasia-123"


def _role_header(client, admin, role: str) -> dict[str, str]:
    email = f"lookup-{role}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={"email": email, "full_name": f"Uji {role}", "password": PASSWORD, "role": role},
    )
    assert resp.status_code in (201, 409), resp.text
    return _login_header(client, email, PASSWORD)


@pytest.mark.parametrize("role", ["finance", "recruiter", "hr", "operations", "business_dev"])
def test_role_alur_bisa_memilih_klien(client, role):
    admin = _auth_header(client)
    created = _create_client(client, admin)
    headers = _role_header(client, admin, role)

    resp = client.get("/api/v1/clients/options", headers=headers)

    assert resp.status_code == 200, resp.text
    # Hanya id + nama: NPWP/PIC/kontrak tetap di belakang CLIENTS_ROLES.
    assert resp.json() == [{"id": created["id"], "name": created["name"]}]


@pytest.mark.parametrize("role", ["finance", "recruiter", "hr", "operations"])
def test_lookup_tidak_membuka_modul_klien(client, role):
    admin = _auth_header(client)
    created = _create_client(client, admin)
    headers = _role_header(client, admin, role)

    assert client.get("/api/v1/clients", headers=headers).status_code == 403
    assert client.get(f"/api/v1/clients/{created['id']}", headers=headers).status_code == 403
    assert client.post("/api/v1/clients", headers=headers, json={"name": "X"}).status_code == 403


def test_karyawan_tidak_bisa_lookup(client):
    admin = _auth_header(client)
    headers = _role_header(client, admin, "karyawan")

    assert client.get("/api/v1/clients/options", headers=headers).status_code == 403
    assert client.get("/api/v1/clients/site-options", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/users/options", headers=headers).status_code == 403


def test_site_options_untuk_hr_bukan_finance(client):
    admin = _auth_header(client)
    created = _create_client(client, admin)
    site = client.post(
        f"/api/v1/clients/{created['id']}/sites",
        headers=admin,
        json={"name": "Gudang A", "latitude": -6.2, "longitude": 106.8, "radius_meters": 150},
    )
    assert site.status_code == 201, site.text

    hr = client.get("/api/v1/clients/site-options", headers=_role_header(client, admin, "hr"))
    assert hr.status_code == 200, hr.text
    assert hr.json() == [
        {
            "id": site.json()["id"],
            "client_name": created["name"],
            "name": "Gudang A",
            "radius_meters": 150,
        }
    ]
    finance = _role_header(client, admin, "finance")
    assert client.get("/api/v1/clients/site-options", headers=finance).status_code == 403


def test_user_options_nama_saja_dan_hanya_yang_aktif(client):
    admin = _auth_header(client)
    recruiter = _role_header(client, admin, "recruiter")
    _role_header(client, admin, "hr")
    users = client.get("/api/v1/auth/users", headers=admin).json()
    hr_id = next(u["id"] for u in users if u["email"] == "lookup-hr@example.com")
    off = client.patch(f"/api/v1/auth/users/{hr_id}", headers=admin, json={"is_active": False})
    assert off.status_code == 200, off.text

    resp = client.get("/api/v1/auth/users/options", headers=recruiter)

    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert all(set(r) == {"id", "full_name"} for r in rows)
    names = {r["full_name"] for r in rows}
    assert "Uji recruiter" in names
    assert "Uji hr" not in names
    # Daftar akun lengkap tetap khusus admin; finance tidak butuh lookup ini.
    assert client.get("/api/v1/auth/users", headers=recruiter).status_code == 403
    finance = _role_header(client, admin, "finance")
    assert client.get("/api/v1/auth/users/options", headers=finance).status_code == 403


def test_lookup_terisolasi_per_tenant(client):
    admin = _auth_header(client)
    _create_client(client, admin, name="PT Milik Default")
    _provision(client, "lookup-b")
    other = _login_header(client, "admin-lookup-b@example.com", "password123")
    _create_client(client, other, name="PT Milik Tenant B")

    mine = client.get("/api/v1/clients/options", headers=_role_header(client, admin, "finance"))
    theirs = client.get("/api/v1/clients/options", headers=other)

    assert [c["name"] for c in mine.json()] == ["PT Milik Default"]
    assert [c["name"] for c in theirs.json()] == ["PT Milik Tenant B"]
    other_users = client.get("/api/v1/auth/users/options", headers=other).json()
    assert [u["full_name"] for u in other_users] == ["Admin lookup-b"]
