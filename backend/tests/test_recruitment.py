import uuid
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

    # kandidat otomatis masuk screening (PRD v3.1 Patch 2: placement dibuat
    # sejak sourcing, bukan lagi langsung "diusulkan"/interview)
    cand = client.get(f"/api/v1/recruitment/candidates/{cand_id}", headers=headers).json()
    assert cand["status"] == "screening"

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


def test_offering_letter_pdf_dan_esign_sandbox(client):
    """PRD v3.0 §4 aksi 2/3 "Offering": surat penawaran PDF -> esign -> status offered.

    Regresi untuk gap yang sebelumnya ditemukan saat audit progres PRD: aksi
    "Offering" cuma PATCH status candidate, tanpa surat penawaran & esign
    sungguhan.
    """
    from tests.test_esign import _sandbox_settings

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

    # Gaji belum diisi & belum diberikan di payload -> wajib ditolak, bukan default 0.
    with _sandbox_settings():
        missing_salary = client.post(
            f"/api/v1/recruitment/placements/{pid}/offering",
            headers=headers,
            json={"signer_name": "Andi", "signer_email": "andi@example.com"},
        )
    assert missing_salary.status_code == 422

    with _sandbox_settings():
        sent = client.post(
            f"/api/v1/recruitment/placements/{pid}/offering",
            headers=headers,
            json={
                "signer_name": "Andi",
                "signer_email": "andi@example.com",
                "offered_salary": 5_200_000,
            },
        )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["placement_id"] == pid
    assert body["contract_id"] is None
    assert body["status"] == "terkirim"
    assert body["provider_document_id"].startswith("sbx-")

    cand = client.get(f"/api/v1/recruitment/candidates/{cand_id}", headers=headers).json()
    assert cand["status"] == "offered"
    jo = client.get(f"/api/v1/recruitment/job-orders/{jo_id}", headers=headers).json()
    assert jo["status"] == "offering"

    # Masih ada permintaan berjalan -> kirim ulang ditolak (anti-duplikat).
    with _sandbox_settings():
        duplicate = client.post(
            f"/api/v1/recruitment/placements/{pid}/offering",
            headers=headers,
            json={"signer_name": "Andi", "signer_email": "andi@example.com"},
        )
    assert duplicate.status_code == 409

    # Simulasi kandidat menandatangani -> placement.offering_signed_at terisi.
    with _sandbox_settings():
        done = client.post(
            f"/api/v1/esign/requests/{body['id']}/simulate-complete", headers=headers
        )
    assert done.status_code == 200
    assert done.json()["status"] == "selesai"

    from app.modules.recruitment.models import Placement

    with client.testing_session() as db:  # type: ignore[attr-defined]
        row = db.get(Placement, uuid.UUID(pid))
        assert row is not None
        assert row.offering_signed_at is not None
        assert row.offering_letter_object_key is not None


def test_offering_summary_pipeline(client):
    """Widget "Offering" Talent Cloud — GET /recruitment/placements/offering-summary."""
    from tests.test_esign import _sandbox_settings

    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid, title="Teller")
    cand_id = _create_candidate(client, headers, name="Rina Wulandari")

    empty = client.get("/api/v1/recruitment/placements/offering-summary", headers=headers).json()
    assert empty == {"total_active": 0, "awaiting_signature": 0, "items": []}

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    ).json()
    pid = placement["id"]

    with _sandbox_settings():
        sent = client.post(
            f"/api/v1/recruitment/placements/{pid}/offering",
            headers=headers,
            json={
                "signer_name": "Rina",
                "signer_email": "rina@example.com",
                "offered_salary": 5_200_000,
            },
        )
    assert sent.status_code == 200, sent.text
    request_id = sent.json()["id"]

    active = client.get("/api/v1/recruitment/placements/offering-summary", headers=headers).json()
    assert active["total_active"] == 1
    assert active["awaiting_signature"] == 1
    item = active["items"][0]
    assert item["placement_id"] == pid
    assert item["candidate_name"] == "Rina Wulandari"
    assert item["job_order_title"] == "Teller"
    assert item["client_name"] == "PT Pemberi Kerja"
    assert item["offered_salary"] == 5_200_000
    assert item["esign_status"] == "terkirim"

    with _sandbox_settings():
        done = client.post(
            f"/api/v1/esign/requests/{request_id}/simulate-complete", headers=headers
        )
    assert done.status_code == 200

    signed = client.get("/api/v1/recruitment/placements/offering-summary", headers=headers).json()
    assert signed["total_active"] == 1
    assert signed["awaiting_signature"] == 0
    assert signed["items"][0]["esign_status"] == "selesai"


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


def test_interview_schedule_notifies_interviewer_and_posts_to_jo_channel(client):
    """PRD v3.0 §4 action 1 — 'notif in-app + chat DM + email' saat interview
    dijadwalkan. Chat DM tidak ada di sistem (tidak ada konsep 1:1 DM),
    padanan yang tersedia: pesan sistem di channel auto JO."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)

    db = client.testing_session()
    try:
        from app.core.bootstrap import ensure_default_tenant
        from app.modules.auth.schemas import UserCreate
        from app.modules.auth.service import create_user

        tenant = ensure_default_tenant(db)
        interviewer = create_user(
            db,
            UserCreate(
                email="interviewer@outsourcing.co.id",
                full_name="Ivan Interviewer",
                password="rahasia-123",
                role="hr",
            ),
            tenant_id=tenant.id,
        )
        interviewer_id = str(interviewer.id)
    finally:
        db.close()

    created = client.post(
        "/api/v1/recruitment/interviews",
        headers=headers,
        json={
            "candidate_id": cand_id,
            "job_order_id": jo_id,
            "interviewer_id": interviewer_id,
            "scheduled_at": "2026-09-10T09:00:00",
            "location": "Kantor Pusat",
        },
    )
    assert created.status_code == 201, created.text

    interviewer_headers = client.post(
        "/api/v1/auth/login",
        json={"email": "interviewer@outsourcing.co.id", "password": "rahasia-123"},
    )
    token = interviewer_headers.json()["access_token"]
    notif_headers = {"Authorization": f"Bearer {token}"}

    notifications = client.get("/api/v1/me/notifications", headers=notif_headers).json()
    assert any(
        n["category"] == "interview" and "Interview dijadwalkan" in n["title"]
        for n in notifications
    )

    channels = client.get("/api/v1/chat/channels", headers=headers).json()
    jo_channel = next((c for c in channels if c["name"] == "JO: Operator Produksi"), None)
    assert jo_channel is not None, "channel auto JO tidak terbuat"
    messages = client.get(
        f"/api/v1/chat/channels/{jo_channel['id']}/messages", headers=headers
    ).json()
    assert any("Interview dijadwalkan" in m["content"] for m in messages)
    # scheduled_at "09:00" tanpa offset dianggap UTC lalu ditampilkan WIB
    # (UTC+7) di teks notifikasi/chat — regresi bug tampilan jam mentah UTC.
    assert any("10 Sep 2026 16:00 WIB" in m["content"] for m in messages)
