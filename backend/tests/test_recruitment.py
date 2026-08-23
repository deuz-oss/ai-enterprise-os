from unittest.mock import patch

from tests.conftest import _auth_header


def _client_id(client, headers) -> str:
    resp = client.post(
        "/api/v1/clients", headers=headers, json={"name": "PT Pemberi Kerja"}
    )
    return resp.json()["id"]


def _create_jo(client, headers, client_id, title="Operator Produksi") -> str:
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": client_id,
            "title": title,
            "headcount": 2,
            "salary_min": 4_500_000,
            "salary_max": 5_500_000,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_candidate(client, headers, name="Andi") -> str:
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": name, "city": "Surabaya", "expected_salary": 5_000_000},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_job_order_lifecycle(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    updated = client.patch(
        f"/api/v1/recruitment/job-orders/{jo_id}",
        headers=headers,
        json={"status": "interview_klien"},
    )
    assert updated.json()["status"] == "interview_klien"

    listed = client.get(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        params={"jo_status": "interview_klien"},
    ).json()
    assert len(listed) == 1


def test_candidate_crud_and_search(client):
    headers = _auth_header(client)
    _create_candidate(client, headers, "Andi Saputra")
    _create_candidate(client, headers, "Bella")

    result = client.get(
        "/api/v1/recruitment/candidates", headers=headers, params={"q": "andi"}
    ).json()
    assert len(result) == 1
    assert result[0]["status"] == "baru"


def test_cv_upload(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    with patch("app.modules.recruitment.service.storage.put_object") as put:
        put.return_value = "key"
        resp = client.post(
            f"/api/v1/recruitment/candidates/{cand_id}/cv",
            headers=headers,
            files={"file": ("cv-andi.pdf", b"%PDF-1.4 cv", "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["cv_file_name"] == "cv-andi.pdf"


def test_placement_flow_updates_statuses(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert placement.status_code == 201
    pid = placement.json()["id"]

    # kandidat otomatis masuk proses interview
    cand = client.get(f"/api/v1/recruitment/candidates/{cand_id}", headers=headers).json()
    assert cand["status"] == "interview"

    # onboard → job order filled karena headcount tercapai (headcount=2, tapi 1 onboard dulu)
    onboarded = client.patch(
        f"/api/v1/recruitment/placements/{pid}",
        headers=headers,
        json={"status": "onboarded"},
    )
    assert onboarded.status_code == 200

    jo = client.get(f"/api/v1/recruitment/job-orders/{jo_id}", headers=headers).json()
    assert jo["status"] == "screening"  # headcount 2, baru 1 yang onboard → belum filled

    # duplikat placement harus ditolak
    duplicate = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert duplicate.status_code == 409


def test_duplicate_job_order_requires_existing_client(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": "00000000-0000-0000-0000-000000000000", "title": "X"},
    )
    assert resp.status_code == 404
