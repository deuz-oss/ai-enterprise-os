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


def test_job_order_structured_benefits_and_working_hours(client):
    """Fase 21 item 1 — field terstruktur benefit & jam kerja, bukan lagi
    numpang di teks bebas description/requirements."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": cid,
            "title": "Operator Produksi",
            "benefits": ["BPJS Kesehatan", "Tunjangan Makan", "Tunjangan Transport"],
            "working_days": ["senin", "selasa", "rabu", "kamis", "jumat"],
            "working_hours_start": "08:00:00",
            "working_hours_end": "17:00:00",
        },
    )
    assert resp.status_code == 201, resp.text
    jo = resp.json()
    assert jo["benefits"] == ["BPJS Kesehatan", "Tunjangan Makan", "Tunjangan Transport"]
    assert jo["working_days"] == ["senin", "selasa", "rabu", "kamis", "jumat"]
    assert jo["working_hours_start"] == "08:00:00"
    assert jo["working_hours_end"] == "17:00:00"

    updated = client.patch(
        f"/api/v1/recruitment/job-orders/{jo['id']}",
        headers=headers,
        json={"benefits": ["BPJS Kesehatan"]},
    )
    assert updated.status_code == 200
    assert updated.json()["benefits"] == ["BPJS Kesehatan"]
    # working_days tidak disentuh oleh update parsial -- tetap seperti semula.
    assert updated.json()["working_days"] == ["senin", "selasa", "rabu", "kamis", "jumat"]


def test_offering_call_recorded_independent_of_offering_letter(client):
    """Fase 21 item 2 — offering call tercatat sebagai aksi terpisah,
    tidak butuh offering letter/esign dulu."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    ).json()
    pid = placement["id"]
    assert placement["offering_call_done"] is False
    assert placement["offering_call_at"] is None

    recorded = client.post(f"/api/v1/recruitment/placements/{pid}/offering-call", headers=headers)
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["offering_call_done"] is True
    assert recorded.json()["offering_call_at"] is not None


def test_interview_schedule_sends_ics_invite_to_candidate_and_interviewer(client):
    """Fase 21 item 5 — invite `.ics` lampiran email, BUKAN OAuth Google
    Calendar (keputusan eksplisit PRD). Verifikasi lewat mock `_smtp_send`
    (tanpa SMTP sungguhan) menangkap pesan + lampiran .ics valid."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers)
    client.patch(
        f"/api/v1/recruitment/candidates/{cand_id}",
        headers=headers,
        json={"email": "andi@kandidat.co.id"},
    )

    sent_messages = []
    with patch(
        "app.modules.notifications.service._smtp_send",
        side_effect=lambda msg: sent_messages.append(msg),
    ):
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
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["To"] == "andi@kandidat.co.id"
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "interview.ics"
    ics_payload = attachments[0].get_payload(decode=True)
    assert b"BEGIN:VEVENT" in ics_payload
    assert b"BEGIN:VCALENDAR" in ics_payload


def test_job_order_template_crud(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/recruitment/job-order-templates",
        headers=headers,
        json={"name": "Template JO Standar", "footer_text": "Dibuat otomatis oleh sistem."},
    )
    assert created.status_code == 201, created.text
    tmpl = created.json()
    assert tmpl["is_active"] is True

    listed = client.get("/api/v1/recruitment/job-order-templates", headers=headers).json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/recruitment/job-order-templates/{tmpl['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_generate_job_order_document_reuses_fase20_pdf_rendering(client):
    """Fase 21 item 4 — generate dokumen JO dari field JO sendiri (benefits/
    working_days/hours dari item 1), reuse penuh `presales.rendering` yang
    sama dipakai Quotation (Fase 20)."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": cid,
            "title": "Operator Produksi",
            "area": "Cikarang",
            "headcount": 3,
            "salary_min": 4_500_000,
            "salary_max": 5_500_000,
            "contract_duration_months": 12,
            "benefits": ["BPJS Kesehatan", "Tunjangan Makan"],
            "working_days": ["senin", "selasa", "rabu", "kamis", "jumat"],
            "working_hours_start": "08:00:00",
            "working_hours_end": "17:00:00",
        },
    ).json()
    assert jo["has_generated_document"] is False

    tmpl = client.post(
        "/api/v1/recruitment/job-order-templates",
        headers=headers,
        json={"name": "Template JO Standar"},
    ).json()

    generated = client.post(
        f"/api/v1/recruitment/job-orders/{jo['id']}/generate-document",
        headers=headers,
        json={"template_id": tmpl["id"]},
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["has_generated_document"] is True
    assert body["generated_document_at"] is not None

    dl = client.get(
        f"/api/v1/recruitment/job-orders/{jo['id']}/generated-document/download-url",
        headers=headers,
    )
    assert dl.status_code == 200
    assert dl.json()["url"]


def test_generate_job_order_document_requires_existing_template(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    resp = client.post(
        f"/api/v1/recruitment/job-orders/{jo_id}/generate-document",
        headers=headers,
        json={"template_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


def test_job_order_fase24_fields_roundtrip(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": cid,
            "title": "Staff Gudang",
            "headcount": 1,
            "remote": True,
            "office_address": "Jl. Industri No. 1",
            "experience_level": "1-3 tahun",
            "contract_detail": "Full Time",
            "industry": "Logistik",
            "position": "Staff",
            "level": "Junior",
            "package_detail": "BPJS + Tunjangan Transport",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["remote"] is True
    assert body["office_address"] == "Jl. Industri No. 1"
    assert body["contract_detail"] == "Full Time"
    assert body["position"] == "Staff"
    assert body["level"] == "Junior"
    assert body["package_detail"] == "BPJS + Tunjangan Transport"

    updated = client.patch(
        f"/api/v1/recruitment/job-orders/{body['id']}",
        headers=headers,
        json={"remote": False, "industry": "Manufaktur"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["remote"] is False
    assert updated.json()["industry"] == "Manufaktur"


def test_candidate_fase24_fields_and_reference(client):
    headers = _auth_header(client)
    first = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={
            "full_name": "Gilang Pratama",
            "gender": "L",
            "birthdate": "1998-05-10",
            "skills_list": ["excel", "forklift"],
            "languages": ["Indonesia", "Inggris"],
            "education_level": "SMA",
        },
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["reference"] == "CAND-00001"
    assert body["skills_list"] == ["excel", "forklift"]
    assert body["languages"] == ["Indonesia", "Inggris"]
    assert body["gender"] == "L"
    assert body["education_level"] == "SMA"

    second = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Hana Putri"}
    )
    assert second.json()["reference"] == "CAND-00002"

    updated = client.patch(
        f"/api/v1/recruitment/candidates/{body['id']}",
        headers=headers,
        json={"skills_list": ["excel", "forklift", "sim-b1"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["skills_list"] == ["excel", "forklift", "sim-b1"]


def test_candidate_experience_crud(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers, "Irfan Maulana")

    created = client.post(
        f"/api/v1/recruitment/candidates/{cand_id}/experiences",
        headers=headers,
        json={
            "company": "PT Contoh Jaya",
            "position": "Admin Gudang",
            "start_date": "2022-01-01",
            "end_date": "2024-06-30",
        },
    )
    assert created.status_code == 201, created.text
    exp = created.json()
    assert exp["company"] == "PT Contoh Jaya"

    listed = client.get(
        f"/api/v1/recruitment/candidates/{cand_id}/experiences", headers=headers
    ).json()
    assert len(listed) == 1

    deleted = client.delete(
        f"/api/v1/recruitment/candidates/experiences/{exp['id']}", headers=headers
    )
    assert deleted.status_code == 204
    assert (
        client.get(f"/api/v1/recruitment/candidates/{cand_id}/experiences", headers=headers).json()
        == []
    )


def test_candidate_activity_log_on_status_change(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers, "Joko Widodo Test")

    updated = client.patch(
        f"/api/v1/recruitment/candidates/{cand_id}",
        headers=headers,
        json={"status": "screening"},
    )
    assert updated.status_code == 200, updated.text

    log = client.get(
        f"/api/v1/recruitment/candidates/{cand_id}/activity-log", headers=headers
    ).json()
    assert any(entry["action"] == "candidate.status_changed" for entry in log)
    changed = next(e for e in log if e["action"] == "candidate.status_changed")
    assert changed["detail"]["from"] == "baru"
    assert changed["detail"]["to"] == "screening"


def test_placement_status_hired_stage(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    cand_id = _create_candidate(client, headers, "Kirana Dewi")
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert placement.status_code == 201, placement.text
    pid = placement.json()["id"]

    hired = client.patch(
        f"/api/v1/recruitment/placements/{pid}",
        headers=headers,
        json={"status": "hired"},
    )
    assert hired.status_code == 200, hired.text


def _create_referring_employee(client, headers, name="Referrer") -> dict:
    resp = client.post("/api/v1/employees", headers=headers, json={"full_name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_employee_gets_referral_code(client):
    headers = _auth_header(client)
    emp = _create_referring_employee(client, headers)
    assert emp["referral_code"].startswith("REF-")


def test_referral_program_setting_toggle(client):
    headers = _auth_header(client)
    default = client.get("/api/v1/recruitment/referral-setting", headers=headers)
    assert default.status_code == 200, default.text
    assert default.json()["is_enabled"] is False

    updated = client.put(
        "/api/v1/recruitment/referral-setting",
        headers=headers,
        json={"is_enabled": True, "reward_amount": 500_000},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_enabled"] is True
    assert updated.json()["reward_amount"] == 500_000


def test_referral_reward_created_when_program_enabled(client):
    headers = _auth_header(client)
    client.put(
        "/api/v1/recruitment/referral-setting",
        headers=headers,
        json={"is_enabled": True, "reward_amount": 250_000},
    )
    referrer = _create_referring_employee(client, headers, "Referrer Aktif")

    cand = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": "Kandidat Referral", "referral_code": referrer["referral_code"]},
    )
    assert cand.status_code == 201, cand.text
    assert cand.json()["referred_by_employee_id"] == referrer["id"]

    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={
            "candidate_id": cand.json()["id"],
            "job_order_id": jo_id,
            "start_date": "2026-06-01",
        },
    )
    assert placement.status_code == 201, placement.text

    rewards = client.get(
        "/api/v1/recruitment/referral-rewards",
        headers=headers,
        params={"employee_id": referrer["id"]},
    ).json()
    assert len(rewards) == 1
    reward = rewards[0]
    assert reward["status"] == "pending"
    assert reward["amount"] == 250_000
    assert reward["eligible_at"] == "2026-09-01"  # start_date + 3 bulan
    assert reward["is_eligible"] is True  # sudah lewat (tanggal berjalan tes 2026-09-04)


def test_referral_reward_not_created_when_program_disabled(client):
    headers = _auth_header(client)
    client.put(
        "/api/v1/recruitment/referral-setting",
        headers=headers,
        json={"is_enabled": False, "reward_amount": 250_000},
    )
    referrer = _create_referring_employee(client, headers, "Referrer Nonaktif")
    cand = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": "Kandidat Tanpa Reward", "referral_code": referrer["referral_code"]},
    )
    assert cand.status_code == 201, cand.text

    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand.json()["id"], "job_order_id": jo_id},
    )
    assert placement.status_code == 201, placement.text

    rewards = client.get(
        "/api/v1/recruitment/referral-rewards",
        headers=headers,
        params={"employee_id": referrer["id"]},
    ).json()
    assert rewards == []


def test_mark_referral_reward_paid(client):
    headers = _auth_header(client)
    client.put(
        "/api/v1/recruitment/referral-setting",
        headers=headers,
        json={"is_enabled": True, "reward_amount": 300_000},
    )
    referrer = _create_referring_employee(client, headers, "Referrer Dibayar")
    cand = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": "Kandidat Dibayar", "referral_code": referrer["referral_code"]},
    ).json()
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)
    client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand["id"], "job_order_id": jo_id},
    )
    reward_id = client.get(
        "/api/v1/recruitment/referral-rewards",
        headers=headers,
        params={"employee_id": referrer["id"]},
    ).json()[0]["id"]

    paid = client.post(
        f"/api/v1/recruitment/referral-rewards/{reward_id}/mark-paid", headers=headers
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"] is not None

    again = client.post(
        f"/api/v1/recruitment/referral-rewards/{reward_id}/mark-paid", headers=headers
    )
    assert again.status_code == 409
