"""Lokasi kantor klien untuk geofencing absensi (Fase 34): CRUD, isolasi
tenant, dan larangan hapus lokasi yang masih dipakai karyawan."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id


def _create_site(client, headers, client_id, **overrides):
    body = {
        "name": "Kantor Pusat Jakarta",
        "address": "Jl. Sudirman No. 1",
        "latitude": "-6.200000",
        "longitude": "106.816666",
        "radius_meters": 100,
    }
    body.update(overrides)
    resp = client.post(f"/api/v1/clients/{client_id}/sites", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_list_update_delete_site(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    site = _create_site(client, headers, cid)
    assert site["name"] == "Kantor Pusat Jakarta"
    assert site["radius_meters"] == 100

    listed = client.get(f"/api/v1/clients/{cid}/sites", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/clients/sites/{site['id']}", headers=headers, json={"radius_meters": 250}
    )
    assert updated.status_code == 200
    assert updated.json()["radius_meters"] == 250

    deleted = client.delete(f"/api/v1/clients/sites/{site['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/clients/{cid}/sites", headers=headers).json() == []


def test_list_all_sites_lintas_klien_bawa_nama_klien(client):
    headers = _auth_header(client)
    cid_a = _client_id(client, headers)
    cid_b = client.post("/api/v1/clients", headers=headers, json={"name": "PT Klien B"}).json()[
        "id"
    ]

    _create_site(client, headers, cid_a, name="Cabang A1")
    _create_site(client, headers, cid_b, name="Cabang B1")

    all_sites = client.get("/api/v1/clients/sites", headers=headers).json()
    names = {(s["client_name"], s["name"]) for s in all_sites}
    assert ("PT Pemberi Kerja", "Cabang A1") in names
    assert ("PT Klien B", "Cabang B1") in names


def test_hapus_site_yang_masih_dipakai_karyawan_ditolak(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    site = _create_site(client, headers, cid)

    emp = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "Karyawan Bersite", "base_salary": 5_000_000},
    ).json()
    client.patch(f"/api/v1/employees/{emp['id']}", headers=headers, json={"site_id": site["id"]})

    blocked = client.delete(f"/api/v1/clients/sites/{site['id']}", headers=headers)
    assert blocked.status_code == 422

    # Lepas tautan dulu -> baru bisa dihapus
    client.patch(f"/api/v1/employees/{emp['id']}", headers=headers, json={"site_id": None})
    ok = client.delete(f"/api/v1/clients/sites/{site['id']}", headers=headers)
    assert ok.status_code == 204
