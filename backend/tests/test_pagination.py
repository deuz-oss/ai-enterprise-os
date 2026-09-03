"""`GET /candidates` dan `GET /job-orders` sebelumnya mengembalikan SELURUH
tabel tanpa batas (temuan audit performa 2026-09-02) — riset MyOHRIS
menunjukkan skala nyata bisa 95 ribu baris. `limit` default 200 + header
`X-Total-Count` ditambah tanpa mengubah bentuk respons (tetap array polos)
supaya konsumen frontend yang ada tidak perlu berubah."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id, _create_candidate, _create_jo


def test_candidates_limit_membatasi_jumlah_baris(client):
    headers = _auth_header(client)
    for i in range(5):
        _create_candidate(client, headers, name=f"Kandidat {i}")

    resp = client.get("/api/v1/recruitment/candidates?limit=2", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert int(resp.headers["X-Total-Count"]) >= 5


def test_candidates_tanpa_limit_pakai_default_dan_kirim_total_count(client):
    headers = _auth_header(client)
    _create_candidate(client, headers, name="Kandidat Default")

    resp = client.get("/api/v1/recruitment/candidates", headers=headers)
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    assert len(resp.json()) <= 200


def test_job_orders_limit_dan_offset(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    for i in range(3):
        _create_jo(client, headers, cid, title=f"Posisi {i}")

    page1 = client.get("/api/v1/recruitment/job-orders?limit=2&offset=0", headers=headers)
    page2 = client.get("/api/v1/recruitment/job-orders?limit=2&offset=2", headers=headers)
    assert len(page1.json()) == 2
    assert len(page2.json()) >= 1
    ids_page1 = {jo["id"] for jo in page1.json()}
    ids_page2 = {jo["id"] for jo in page2.json()}
    assert ids_page1.isdisjoint(ids_page2)


def test_candidates_limit_di_atas_batas_ditolak(client):
    headers = _auth_header(client)
    resp = client.get("/api/v1/recruitment/candidates?limit=5000", headers=headers)
    assert resp.status_code == 422
