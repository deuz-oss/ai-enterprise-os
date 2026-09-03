"""Guard delete untuk entitas induk yang masih direferensikan (audit
2026-09-02) — sebelumnya `DELETE /job-orders/{id}` dkk. selalu 500
IntegrityError mentah kalau masih ada baris terkait (Placement,
InterviewSchedule, Payslip, dst.), tanpa satu pun test yang menangkap ini.
Fokus di sini: guard-nya benar-benar memblokir (422 jelas, bukan 500) DAN
delete tetap berjalan normal kalau memang tidak ada referensi."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id, _create_candidate, _create_jo


def test_delete_job_order_diblokir_kalau_masih_ada_placement(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert placement.status_code == 201, placement.text

    resp = client.delete(f"/api/v1/recruitment/job-orders/{jo_id}", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "placements" in resp.json()["detail"]


def test_delete_job_order_tanpa_placement_berhasil(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    resp = client.delete(f"/api/v1/recruitment/job-orders/{jo_id}", headers=headers)
    assert resp.status_code == 204, resp.text

    check = client.get("/api/v1/recruitment/job-orders", headers=headers)
    assert jo_id not in [jo["id"] for jo in check.json()]


def test_delete_candidate_diblokir_kalau_masih_ada_placement(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)
    client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )

    resp = client.delete(f"/api/v1/recruitment/candidates/{cand_id}", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "placements" in resp.json()["detail"]


def test_delete_client_diblokir_kalau_masih_ada_job_order(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    _create_jo(client, headers, cid)

    resp = client.delete(f"/api/v1/clients/{cid}", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "job_orders" in resp.json()["detail"]


def test_delete_client_tanpa_job_order_berhasil(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    resp = client.delete(f"/api/v1/clients/{cid}", headers=headers)
    assert resp.status_code == 204, resp.text
