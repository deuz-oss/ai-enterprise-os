"""Nomor auto-generate (request_id Job Order, contract_no kontrak kerja)
sebelumnya berbasis COUNT(*) tanpa UniqueConstraint sama sekali -- tabrakan
sukses tersimpan diam-diam, tanpa satu pun test yang menangkapnya (temuan
audit 2026-09-02). Fokus di sini: request_id/contract_no yang SAMA
persis (dikirim eksplisit dua kali) sekarang ditolak jelas (409), bukan
duplikat diam-diam."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id, _create_jo


def test_job_order_request_id_eksplisit_duplikat_ditolak(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    first = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": cid,
            "title": "Posisi A",
            "headcount": 1,
            "request_id": "JO/CUSTOM/0001",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": cid,
            "title": "Posisi B",
            "headcount": 1,
            "request_id": "JO/CUSTOM/0001",
        },
    )
    assert second.status_code == 409, second.text


def test_job_order_request_id_auto_generate_tidak_pernah_duplikat(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    ids = [_create_jo(client, headers, cid, title=f"Posisi {i}") for i in range(3)]
    all_jo = client.get("/api/v1/recruitment/job-orders", headers=headers).json()
    generated = [jo["request_id"] for jo in all_jo if jo["id"] in ids]
    assert len(generated) == len(set(generated)) == 3
