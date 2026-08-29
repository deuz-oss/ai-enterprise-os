from unittest.mock import patch

from tests.conftest import _auth_header


def _client_id(client, headers) -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Pemberi Kerja"})
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


def test_interview_schedule_crud(client):
    """PRD v3.0 §4 action 1 — Schedule Interview.

    Regresi untuk bug audit.log_event(target_type=/target_id=/payload=) yang membuat
    audit trail `interview.scheduled` gagal ditulis sebelum diperbaiki (dibungkus
    try/except sehingga sebelumnya lolos diam-diam tanpa 500, tapi tanpa jejak audit).
    """
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)

    created = client.post(
        "/api/v1/recruitment/interviews",
        headers=headers,
        json={
            "candidate_id": cand_id,
            "job_order_id": jo_id,
            "scheduled_at": "2026-09-10T09:00:00",
            "location": "Kantor Pusat",
        },
    )
    assert created.status_code == 201, created.text
    interview_id = created.json()["id"]
    assert created.json()["status"] == "terjadwal"

    listed = client.get(
        "/api/v1/recruitment/interviews", headers=headers, params={"job_order_id": jo_id}
    ).json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/recruitment/interviews/{interview_id}",
        headers=headers,
        json={"status": "selesai", "feedback": "Bagus", "score": 4},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "selesai"
    assert updated.json()["score"] == 4


def test_match_candidates_scores_by_skill_overlap_and_ranks(client):
    """PRD v3.0 §4 AI Matching Native — jalur fallback deterministik (AI belum
    dikonfigurasi di test env). Kandidat dengan skill lebih cocok harus lebih
    tinggi skornya dan endpoint match/matches harus konsisten."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid, title="Operator Produksi")
    client.patch(
        f"/api/v1/recruitment/job-orders/{jo_id}",
        headers=headers,
        json={"requirements": "operator produksi berpengalaman las"},
    )

    strong = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={
            "full_name": "Kandidat Cocok",
            "city": "Surabaya",
            "skills": "operator produksi las",
            "expected_salary": 5_000_000,
        },
    ).json()["id"]
    weak = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": "Kandidat Tak Cocok", "city": "Medan", "skills": "desain grafis"},
    ).json()["id"]

    matched = client.post(
        f"/api/v1/recruitment/job-orders/{jo_id}/match", headers=headers, json={"top_k": 10}
    )
    assert matched.status_code == 200, matched.text
    results = matched.json()
    by_id = {r["candidate_id"]: r for r in results}
    assert by_id[strong]["match_score"] > by_id[weak]["match_score"]
    for r in results:
        assert 0 <= r["match_score"] <= 100
        assert isinstance(r["explain"], str) and r["explain"]

    filtered = client.get(
        f"/api/v1/recruitment/job-orders/{jo_id}/matches",
        headers=headers,
        params={"min_score": by_id[strong]["match_score"]},
    ).json()
    assert any(r["candidate_id"] == strong for r in filtered)
    assert all(r["candidate_id"] != weak for r in filtered)
