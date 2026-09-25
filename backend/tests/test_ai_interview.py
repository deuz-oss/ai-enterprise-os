"""AI Interview (PRD v3.1 Patch 4) — template CRUD, invite, sesi kandidat via
token publik, skoring AI (best-effort — AI dipaksa nonaktif di test lewat
conftest), dan gate review manusia wajib."""

from datetime import UTC, datetime, timedelta

from tests.conftest import _auth_header


def _client_id(client, headers) -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Interview AI"})
    return resp.json()["id"]


def _create_candidate(client, headers, name="Budi", email="budi@example.com") -> str:
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": name, "email": email, "city": "Jakarta"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _template_payload(**overrides) -> dict:
    payload = {
        "title": "Interview CS",
        "objective": "Menilai kesiapan CS",
        "mode": "async_text",
        "questions": [
            {
                "id": "q1",
                "order": 1,
                "type": "open_ended",
                "prompt": "Ceritakan pengalaman Anda menangani komplain pelanggan.",
                "criterion_keys": ["komunikasi"],
            },
            {
                "id": "q2",
                "order": 2,
                "type": "open_ended",
                "prompt": "Bagaimana Anda menangani tekanan kerja?",
                "criterion_keys": ["ketahanan"],
            },
        ],
        "criteria": [
            {"key": "komunikasi", "label": "Komunikasi", "weight": 0.5},
            {"key": "ketahanan", "label": "Ketahanan Kerja", "weight": 0.5},
        ],
    }
    payload.update(overrides)
    return payload


def _create_active_template(client, headers, **payload_overrides) -> dict:
    payload = _template_payload(**payload_overrides)
    created = client.post("/api/v1/ai-interview/templates", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    template = created.json()
    activated = client.patch(
        f"/api/v1/ai-interview/templates/{template['id']}",
        headers=headers,
        json={"status": "aktif"},
    )
    assert activated.status_code == 200
    return activated.json()


def _consent(client, token: str) -> None:
    """Fase 0: kandidat wajib menyetujui pemrosesan data sebelum mulai."""
    resp = client.post(f"/api/v1/ai-interview/session/{token}/consent")
    assert resp.status_code == 204, resp.text


def _invite(client, headers, template_id, candidate_id, consent: bool = True) -> dict:
    invite = client.post(
        f"/api/v1/ai-interview/templates/{template_id}/invite",
        headers=headers,
        json={"candidate_ids": [candidate_id]},
    )
    assert invite.status_code == 200, invite.text
    invited = invite.json()["invited"][0]
    if consent:
        _consent(client, invited["invite_token"])
    return invited


def test_template_crud_roundtrips_questions_and_criteria(client):
    admin = _auth_header(client)
    created = client.post("/api/v1/ai-interview/templates", headers=admin, json=_template_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["mode"] == "async_text"
    assert len(body["questions"]) == 2
    assert body["questions"][0]["criterion_keys"] == ["komunikasi"]
    assert len(body["criteria"]) == 2

    fetched = client.get(f"/api/v1/ai-interview/templates/{body['id']}", headers=admin)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Interview CS"

    listed = client.get("/api/v1/ai-interview/templates", headers=admin).json()
    assert any(t["id"] == body["id"] for t in listed)


def test_invite_requires_active_template(client):
    admin = _auth_header(client)
    created = client.post(
        "/api/v1/ai-interview/templates", headers=admin, json=_template_payload()
    ).json()
    cand_id = _create_candidate(client, admin)

    blocked = client.post(
        f"/api/v1/ai-interview/templates/{created['id']}/invite",
        headers=admin,
        json={"candidate_ids": [cand_id]},
    )
    assert blocked.status_code == 422


def test_candidate_session_flow_submit_leaves_submitted_when_ai_unconfigured(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin)
    cand_id = _create_candidate(client, admin)

    invite = client.post(
        f"/api/v1/ai-interview/templates/{template['id']}/invite",
        headers=admin,
        json={"candidate_ids": [cand_id]},
    )
    assert invite.status_code == 200, invite.text
    invite_body = invite.json()
    assert len(invite_body["invited"]) == 1
    # SMTP no-op tapi tetap dianggap "terkirim" (fire-and-forget, tidak melempar).
    assert invite_body["invited"][0]["email_sent"] is True
    token = invite_body["invited"][0]["invite_token"]
    response_id = invite_body["invited"][0]["response_id"]

    # Sesi publik: TANPA header auth sama sekali.
    session = client.get(f"/api/v1/ai-interview/session/{token}")
    assert session.status_code == 200, session.text
    session_body = session.json()
    assert session_body["title"] == "Interview CS"
    assert len(session_body["questions"]) == 2
    # Kandidat TIDAK boleh lihat criterion_keys/weight (bocor bobot penilaian).
    assert "criterion_keys" not in session_body["questions"][0]
    assert "weight" not in session_body["questions"][0]

    # Fase 0: tanpa persetujuan, interview tidak bisa dimulai.
    assert session_body["consent_given"] is False
    assert "UU No. 27 Tahun 2022" in session_body["consent_text"]
    blocked = client.post(f"/api/v1/ai-interview/session/{token}/start")
    assert blocked.status_code == 403
    _consent(client, token)

    start = client.post(f"/api/v1/ai-interview/session/{token}/start")
    assert start.status_code == 204

    for qid, text in [("q1", "Saya dengarkan dulu keluhannya."), ("q2", "Saya tetap tenang.")]:
        ans = client.post(
            f"/api/v1/ai-interview/session/{token}/answer",
            json={"question_id": qid, "answer_text": text},
        )
        assert ans.status_code == 204, ans.text

    submit = client.post(f"/api/v1/ai-interview/session/{token}/submit")
    assert submit.status_code == 200, submit.text
    # AI_BASE_URL kosong di test -> scoring gagal, status tetap "terkirim" bukan "dinilai".
    assert submit.json()["status"] == "terkirim"

    again = client.post(f"/api/v1/ai-interview/session/{token}/submit")
    assert again.status_code == 422

    # Sisi staf: lihat detail penuh termasuk jawaban.
    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["status"] == "terkirim"
    assert detail_body["review_status"] == "menunggu_review"
    assert len(detail_body["answers"]) == 2

    score = client.post(f"/api/v1/ai-interview/responses/{response_id}/score", headers=admin)
    assert score.status_code == 503  # AI belum aktif di lingkungan test


def test_review_gate_required_before_final_and_adjusted_override(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin)
    cand_id = _create_candidate(client, admin)
    invite = client.post(
        f"/api/v1/ai-interview/templates/{template['id']}/invite",
        headers=admin,
        json={"candidate_ids": [cand_id]},
    ).json()
    token = invite["invited"][0]["invite_token"]
    response_id = invite["invited"][0]["response_id"]

    # Belum submit -> belum bisa direview.
    too_early = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disetujui"},
    )
    assert too_early.status_code == 422

    _consent(client, token)
    client.post(f"/api/v1/ai-interview/session/{token}/start")
    client.post(
        f"/api/v1/ai-interview/session/{token}/answer",
        json={"question_id": "q1", "answer_text": "Jawaban 1"},
    )
    client.post(f"/api/v1/ai-interview/session/{token}/submit")

    reviewed = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={
            "review_status": "disesuaikan",
            "review_notes": "Skor AI gagal, dinilai manual",
            "ai_score_overall": 82,
            "ai_score_breakdown": [
                {"criterion_key": "komunikasi", "score": 82, "reasoning": "Baik"}
            ],
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["review_status"] == "disesuaikan"
    assert body["ai_score_overall"] == 82
    assert body["reviewed_by"] is not None
    assert body["reviewed_at"] is not None

    # review_status tidak boleh diset balik ke pending lewat endpoint ini.
    bad = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "menunggu_review"},
    )
    assert bad.status_code == 422


def test_expired_token_rejected_and_resend_invite_reactivates(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin)
    cand_id = _create_candidate(client, admin)
    invite = client.post(
        f"/api/v1/ai-interview/templates/{template['id']}/invite",
        headers=admin,
        json={"candidate_ids": [cand_id]},
    ).json()
    token = invite["invited"][0]["invite_token"]
    response_id = invite["invited"][0]["response_id"]

    from app.core.database import parse_uuid
    from app.modules.ai_interview.models import AIInterviewResponse

    db = client.testing_session()
    try:
        row = db.get(AIInterviewResponse, parse_uuid(response_id))
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    expired = client.get(f"/api/v1/ai-interview/session/{token}")
    assert expired.status_code == 410

    resent = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/resend-invite", headers=admin
    )
    assert resent.status_code == 200, resent.text
    new_token = resent.json()  # response_model AIInterviewResponseOut -- token bukan field publik
    assert new_token["status"] == "diundang"

    db2 = client.testing_session()
    try:
        row2 = db2.get(AIInterviewResponse, parse_uuid(response_id))
        fresh_token = row2.invite_token
        assert fresh_token != token
    finally:
        db2.close()

    reactivated = client.get(f"/api/v1/ai-interview/session/{fresh_token}")
    assert reactivated.status_code == 200


def test_unknown_token_returns_404(client):
    resp = client.get("/api/v1/ai-interview/session/does-not-exist-token")
    assert resp.status_code == 404


# ---------- AI Interview Fase 2: percakapan suara real-time ----------


def test_public_session_reports_mode(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin)
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)

    session = client.get(f"/api/v1/ai-interview/session/{invited['invite_token']}")
    assert session.status_code == 200
    assert session.json()["mode"] == "async_text"


def test_voice_start_rejects_wrong_mode(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin)  # default mode = async_text
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)

    resp = client.post(f"/api/v1/ai-interview/session/{invited['invite_token']}/voice/start")
    assert resp.status_code == 422


def test_voice_start_requires_configured_infra(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)

    # conftest forces LIVEKIT_* empty -- voice_interview_configured is False.
    resp = client.post(f"/api/v1/ai-interview/session/{invited['invite_token']}/voice/start")
    assert resp.status_code == 503


def test_voice_start_mints_token_and_dispatches_agent(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_url", "ws://livekit.test:7880")
    monkeypatch.setattr(settings, "livekit_api_key", "test-key")
    monkeypatch.setattr(settings, "livekit_api_secret", "test-secret-32-bytes-minimum-ok")
    monkeypatch.setattr(settings, "stt_base_url", "http://stt.test")
    monkeypatch.setattr(settings, "ai_base_url", "https://api.test/v1")

    dispatched: dict = {}

    class _FakeAgentDispatch:
        async def create_dispatch(self, request):
            dispatched["room"] = request.room
            dispatched["agent_name"] = request.agent_name
            dispatched["metadata"] = request.metadata

    class _FakeLiveKitAPI:
        def __init__(self, *a, **kw):
            self.agent_dispatch = _FakeAgentDispatch()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    import app.modules.ai_interview.service as service_module

    monkeypatch.setattr(service_module.lk_api, "LiveKitAPI", _FakeLiveKitAPI)

    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]

    resp = client.post(f"/api/v1/ai-interview/session/{token}/voice/start")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"] == "ws://livekit.test:7880"
    assert isinstance(body["token"], str) and len(body["token"]) > 20
    assert dispatched["agent_name"] == "ai-interview-agent"
    assert dispatched["metadata"] == token

    session = client.get(f"/api/v1/ai-interview/session/{token}")
    assert session.json()["status"] == "berlangsung"


_TEST_AGENT_SECRET = "test-livekit-secret-for-agent-signature"


def _agent_headers(monkeypatch, token: str) -> dict[str, str]:
    """Header tanda tangan agent (HMAC LIVEKIT_API_SECRET) untuk endpoint
    khusus agent -- kandidat yang cuma punya invite_token tidak bisa."""
    from app.core.config import get_settings
    from app.modules.ai_interview.service import agent_signature

    monkeypatch.setattr(get_settings(), "livekit_api_secret", _TEST_AGENT_SECRET)
    return {"X-Agent-Signature": agent_signature(token)}


def test_voice_context_includes_criterion_keys_unlike_public_session(client, monkeypatch):
    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]

    ctx = client.get(
        f"/api/v1/ai-interview/session/{token}/voice/context",
        headers=_agent_headers(monkeypatch, token),
    )
    assert ctx.status_code == 200, ctx.text
    body = ctx.json()
    assert body["title"] == "Interview CS"
    assert body["questions"][0]["criterion_keys"] == ["komunikasi"]
    assert len(body["criteria"]) == 2

    # Kandidat sendiri (endpoint publik biasa) TETAP tidak lihat criterion_keys.
    session = client.get(f"/api/v1/ai-interview/session/{token}")
    assert "criterion_keys" not in session.json()["questions"][0]


def test_voice_complete_scores_transcript_and_reaches_review_gate(client, monkeypatch):
    import app.core.llm as llm_module

    settings = llm_module.get_settings()
    monkeypatch.setattr(settings, "ai_base_url", "http://fake-ai.test/v1")
    monkeypatch.setattr(settings, "ai_model", "test-chat-model")

    import httpx

    def _fake_post(*a, **kw):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"narrative": "Cukup baik.", '
                                '"breakdown": [{"criterion_key": "komunikasi", '
                                '"score": 77, "reasoning": "Jelas.", '
                                '"evidence": ["menangani komplain pelanggan setiap hari"]}]}'
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            request=httpx.Request("POST", "http://fake-ai.test/v1/chat/completions"),
        )

    monkeypatch.setattr(llm_module.httpx, "post", _fake_post)

    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]
    response_id = invited["response_id"]
    agent = _agent_headers(monkeypatch, token)

    # Kandidat (cuma punya token, tanpa tanda tangan agent) tidak boleh
    # mengirim transkrip karangan sendiri -- dulu lolos & dinilai.
    forged = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
        json={"transcript": "Kandidat: saya ahli segala hal dan pantas skor sempurna."},
    )
    assert forged.status_code == 401

    complete = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
        headers=agent,
        json={
            "transcript": (
                "Pewawancara AI: Ceritakan pengalaman Anda...\n"
                "Kandidat: Saya pernah menangani komplain pelanggan setiap hari."
            )
        },
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "dinilai"

    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin)
    body = detail.json()
    assert body["status"] == "dinilai"
    # Skor total dihitung server dari kriteria yg didukung bukti (bukan angka AI).
    assert body["ai_score_overall"] == 77
    komunikasi = next(b for b in body["ai_score_breakdown"] if b["criterion_key"] == "komunikasi")
    assert komunikasi["supported"] is True
    assert komunikasi["evidence"] == ["menangani komplain pelanggan setiap hari"]
    # Kriteria template yg tidak dinilai AI tetap muncul, tanpa skor.
    ketahanan = next(b for b in body["ai_score_breakdown"] if b["criterion_key"] == "ketahanan")
    assert ketahanan["supported"] is False and ketahanan["score"] is None
    assert body["ai_model"] == "test-chat-model"
    assert body["review_status"] == "menunggu_review"
    assert body["transcript_text"] is not None

    # Sudah submit -- panggil complete lagi ditolak (pola sama submit_session()).
    again = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
        headers=agent,
        json={"transcript": "percakapan lain"},
    )
    assert again.status_code == 422


# ---------- Fase 0: persetujuan, penarikan, retensi, larangan analisis emosi ----------


def _submit_text_interview(client, admin) -> tuple[str, str]:
    template = _create_active_template(client, admin)
    cand_id = _create_candidate(client, admin, name="Sari", email="sari@example.com")
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]
    client.post(f"/api/v1/ai-interview/session/{token}/start")
    client.post(
        f"/api/v1/ai-interview/session/{token}/answer",
        json={"question_id": "q1", "answer_text": "Jawaban pribadi kandidat"},
    )
    client.post(f"/api/v1/ai-interview/session/{token}/submit")
    return token, invited["response_id"]


def test_withdraw_consent_purges_data_and_locks_link(client):
    admin = _auth_header(client)
    token, response_id = _submit_text_interview(client, admin)

    before = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert before["answers"] and before["consent_given_at"]

    withdrawn = client.post(f"/api/v1/ai-interview/session/{token}/withdraw-consent")
    assert withdrawn.status_code == 204
    # Idempoten.
    assert client.post(f"/api/v1/ai-interview/session/{token}/withdraw-consent").status_code == 204

    after = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert after["answers"] == []
    assert after["transcript_text"] is None and after["ai_score_overall"] is None
    assert after["purge_reason"] == "penarikan_persetujuan"
    assert after["consent_withdrawn_at"] is not None

    # Halaman kandidat tetap bisa menampilkan status "sudah ditarik"...
    session = client.get(f"/api/v1/ai-interview/session/{token}")
    assert session.status_code == 200 and session.json()["data_withdrawn"] is True
    # ...tapi aksi apa pun ditolak, dan staf tidak bisa menilai/mereview data yang sudah dihapus.
    assert client.post(f"/api/v1/ai-interview/session/{token}/start").status_code == 410
    review = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disetujui"},
    )
    assert review.status_code == 409


def test_retention_purges_old_responses(client):
    from datetime import UTC, datetime, timedelta

    from app.modules.ai_interview.models import AIInterviewResponse

    admin = _auth_header(client)
    _, response_id = _submit_text_interview(client, admin)

    db = client.testing_session()
    try:
        row = db.get(AIInterviewResponse, __import__("uuid").UUID(response_id))
        row.submitted_at = datetime.now(UTC) - timedelta(days=200)  # > default 180
        db.commit()
    finally:
        db.close()

    # Safety-net: membuka daftar respons langsung membersihkan yang kedaluwarsa.
    rows = client.get("/api/v1/ai-interview/responses", headers=admin).json()
    purged = next(r for r in rows if r["id"] == response_id)
    assert purged["answers"] == [] and purged["purge_reason"] == "retensi"

    settings = client.get("/api/v1/ai-interview/settings", headers=admin)
    assert settings.status_code == 200 and settings.json()["retention_days"] == 180
    too_short = client.put(
        "/api/v1/ai-interview/settings", headers=admin, json={"retention_days": 7}
    )
    assert too_short.status_code == 422
    updated = client.put(
        "/api/v1/ai-interview/settings", headers=admin, json={"retention_days": 90}
    )
    assert updated.status_code == 200 and updated.json()["retention_days"] == 90
    run = client.post("/api/v1/ai-interview/retention/run", headers=admin)
    assert run.status_code == 200 and run.json()["purged"] == 0


def test_template_rejects_emotion_or_voice_criteria(client):
    admin = _auth_header(client)
    payload = _template_payload()
    payload["criteria"] = [{"key": "nada", "label": "Nada suara & intonasi"}]
    resp = client.post("/api/v1/ai-interview/templates", headers=admin, json=payload)
    assert resp.status_code == 422
    assert "nada suara" in resp.text


def test_scoring_prompt_forbids_emotion_inference():
    from app.modules.ai_interview.service import _SCORE_SYSTEM_PROMPT

    assert "DILARANG menilai" in _SCORE_SYSTEM_PROMPT
    assert "emosi" in _SCORE_SYSTEM_PROMPT and "aksen" in _SCORE_SYSTEM_PROMPT


def test_candidate_forget_also_purges_ai_interview_data(client):
    """Hak hapus subjek (talentpool forget) dulu meninggalkan jawaban,
    transkrip & skor AI Interview utuh."""
    admin = _auth_header(client)
    _, response_id = _submit_text_interview(client, admin)
    cand_id = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()[
        "candidate_id"
    ]
    forget = client.post(f"/api/v1/talentpool/candidates/{cand_id}/forget", headers=admin)
    assert forget.status_code == 200, forget.text
    assert forget.json()["ai_interviews"] == 1

    after = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert after["answers"] == [] and after["purge_reason"] == "penghapusan_subjek"


# ---------- Fase 1 roadmap #5: rubrik + kutipan bukti ----------


def test_rubric_drops_fabricated_and_interviewer_quotes():
    from app.modules.ai_interview.service import _candidate_lines, build_rubric_breakdown

    criteria = [
        {"key": "komunikasi", "label": "Komunikasi", "weight": 2},
        {"key": "teknis", "label": "Teknis", "weight": 1},
        {"key": "kerjasama", "label": "Kerja sama", "weight": 1},
    ]
    transcript = (
        "Pewawancara AI: Ceritakan cara menangani komplain pelanggan.\n"
        "Kandidat: Saya selalu mendengarkan keluhan pelanggan dulu, lalu menawarkan solusi."
    )
    ai_result = {
        "overall": 99,  # diabaikan -- total dihitung server
        "breakdown": [
            {
                "criterion_key": "komunikasi",
                "score": 80,
                "evidence": ["Mendengarkan keluhan pelanggan dulu", "Saya pakai CRM Salesforce"],
            },
            # Kutipan hanya ada di kalimat PEWAWANCARA -> tidak sah.
            {"criterion_key": "teknis", "score": 90, "evidence": ["menangani komplain pelanggan"]},
            # Kriteria di luar template -> diabaikan.
            {"criterion_key": "bocor", "score": 100, "evidence": ["menawarkan solusi"]},
        ],
    }
    breakdown, overall = build_rubric_breakdown(ai_result, criteria, _candidate_lines(transcript))
    by_key = {b["criterion_key"]: b for b in breakdown}
    assert set(by_key) == {"komunikasi", "teknis", "kerjasama"}
    assert by_key["komunikasi"]["evidence"] == ["Mendengarkan keluhan pelanggan dulu"]
    assert by_key["komunikasi"]["dropped_quotes"] == 1
    assert by_key["teknis"]["supported"] is False
    assert by_key["kerjasama"]["score"] is None
    assert overall == 80  # hanya kriteria yg didukung bukti


def test_rubric_quote_rules():
    from app.modules.ai_interview.service import _norm, _verify_quote

    hay = _norm("Saya bekerja 3 tahun di gudang, mengatur stok dan pengiriman barang.")
    assert _verify_quote("mengatur stok dan pengiriman", hay)
    assert _verify_quote("Saya bekerja 3 tahun ... pengiriman barang", hay)  # elipsis
    assert not _verify_quote("stok", hay)  # < 3 kata
    assert not _verify_quote("mengelola stok dan pengiriman", hay)  # parafrase


def test_scoring_uses_dedicated_model_when_configured(client, monkeypatch):
    import app.core.llm as llm_module
    import httpx

    settings = llm_module.get_settings()
    monkeypatch.setattr(settings, "ai_base_url", "http://fake-ai.test/v1")
    monkeypatch.setattr(settings, "ai_model", "model-umum")
    monkeypatch.setattr(settings, "ai_scoring_model", "sahabat-ai-uji")
    seen: list[str] = []

    def _fake_post(url, json=None, **kw):
        seen.append(json["model"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"narrative": "-", "breakdown": []}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(llm_module.httpx, "post", _fake_post)
    admin = _auth_header(client)
    _, response_id = _submit_text_interview(client, admin)
    body = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert seen and seen[-1] == "sahabat-ai-uji"
    assert body["ai_model"] == "sahabat-ai-uji"
    assert body["ai_score_overall"] is None  # tanpa bukti -> tidak ada skor total


# ---------- Fase 2 roadmap: autentikasi agent, rekaman sesi, transkrip rapi ----------


def _voice_response(client, admin, *, start: bool = True) -> tuple[str, str]:
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin, name="Rina", email="rina@example.com")
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]
    if start:
        client.post(f"/api/v1/ai-interview/session/{token}/start")
    return token, invited["response_id"]


def test_agent_only_endpoints_reject_candidate_token(client, monkeypatch):
    """Kandidat memegang invite_token yang sama -- dulu bisa membaca kriteria
    & bobot penilaian lewat voice/context. Sekarang wajib tanda tangan agent."""
    admin = _auth_header(client)
    token, _ = _voice_response(client, admin)
    _agent_headers(monkeypatch, token)  # secret terpasang di server

    base = f"/api/v1/ai-interview/session/{token}"
    assert client.get(f"{base}/voice/context").status_code == 401
    bad = {"X-Agent-Signature": "0" * 64}
    assert client.get(f"{base}/voice/context", headers=bad).status_code == 401
    assert (
        client.post(
            f"{base}/voice/recording", content=b"OggS", headers={"Content-Type": "audio/ogg"}
        ).status_code
        == 401
    )


def test_agent_signature_fails_closed_without_secret(client, monkeypatch):
    """LIVEKIT_API_SECRET kosong -> endpoint agent tertutup, bukan terbuka."""
    from app.core.config import get_settings

    admin = _auth_header(client)
    token, _ = _voice_response(client, admin)
    monkeypatch.setattr(get_settings(), "livekit_api_secret", None)
    ctx = client.get(
        f"/api/v1/ai-interview/session/{token}/voice/context",
        headers={"X-Agent-Signature": "apa-saja"},
    )
    assert ctx.status_code == 401


def test_recording_upload_url_and_purge(client, monkeypatch):
    admin = _auth_header(client)
    token, response_id = _voice_response(client, admin)
    agent = _agent_headers(monkeypatch, token)
    url = f"/api/v1/ai-interview/session/{token}/voice/recording"
    audio = b"OggS" + b"\x00" * 2048

    wrong_type = client.post(url, content=audio, headers={**agent, "Content-Type": "text/plain"})
    assert wrong_type.status_code == 422

    stored = client.post(url, content=audio, headers={**agent, "Content-Type": "audio/ogg"})
    assert stored.status_code == 204, stored.text
    again = client.post(url, content=audio, headers={**agent, "Content-Type": "audio/ogg"})
    assert again.status_code == 409  # satu rekaman per respons

    body = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert body["has_recording"] is True and body["recording_size_bytes"] == len(audio)

    link = client.get(f"/api/v1/ai-interview/responses/{response_id}/recording-url", headers=admin)
    assert link.status_code == 200, link.text
    assert link.json()["channels"] == ["Kandidat", "Pewawancara AI"]
    played = client.get(link.json()["url"])  # mode storage lokal di test
    assert played.status_code == 200 and played.content == audio
    # Rekaman biometrik tidak boleh tertinggal di cache browser reviewer.
    assert played.headers["cache-control"] == "no-store"

    # Penarikan persetujuan menghapus FILE rekaman, bukan cuma kolomnya.
    assert client.post(f"/api/v1/ai-interview/session/{token}/withdraw-consent").status_code == 204
    after = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert after["has_recording"] is False
    assert client.get(link.json()["url"]).status_code == 404
    gone = client.get(f"/api/v1/ai-interview/responses/{response_id}/recording-url", headers=admin)
    assert gone.status_code == 409


def test_consent_text_mentions_recording():
    from app.modules.ai_interview.service import CONSENT_VERSION, consent_text

    text = consent_text(180)
    assert "direkam" in text and "rekaman" in text
    assert CONSENT_VERSION == "2026-09-24.3"


# ---------- Fase 3 roadmap: mode rekaman jawaban (async_recording) ----------


def _recording_setup(client, monkeypatch, transcripts: list[str]):
    """Template mode rekaman + kandidat bersetuju; STT di-mock berurutan."""
    from app.core.config import get_settings
    from app.modules.ai_interview import service as svc

    monkeypatch.setattr(get_settings(), "stt_base_url", "http://stt.test/v1")
    queue = list(transcripts)

    def fake_stt(data, mime):
        text = queue.pop(0)
        # Timestamp kata sintetis: 0,5 detik per kata.
        words = [[i * 0.5, i * 0.5 + 0.4, w] for i, w in enumerate(text.split())]
        return text, words

    monkeypatch.setattr(svc, "_stt_transcribe", fake_stt)
    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="async_recording")
    cand_id = _create_candidate(client, admin, name="Dewi", email="dewi@example.com")
    invited = _invite(client, admin, template["id"], cand_id)
    return admin, invited["invite_token"], invited["response_id"]


def _upload(client, token, qid, audio=b"\x1aE\xdf\xa3webm-audio", ctype="audio/webm"):
    return client.post(
        f"/api/v1/ai-interview/session/{token}/answers/{qid}/audio?duration_sec=12.5",
        content=audio,
        headers={"Content-Type": ctype},
    )


def test_recording_answer_transcribed_and_submitted(client, monkeypatch):
    admin, token, response_id = _recording_setup(
        client,
        monkeypatch,
        ["Saya dengarkan keluhan pelanggan dulu.", "Saya tetap tenang dan bikin prioritas."],
    )
    up = _upload(client, token, "q1")
    assert up.status_code == 202, up.text
    session = client.get(f"/api/v1/ai-interview/session/{token}").json()
    rec = {r["question_id"]: r for r in session["recorded_answers"]}
    # TestClient menjalankan background task sebelum post() kembali.
    assert rec["q1"]["status"] == "ready"
    assert rec["q1"]["transcript"] == "Saya dengarkan keluhan pelanggan dulu."
    assert session["max_attempts"] == 3

    assert _upload(client, token, "q2").status_code == 202
    submit = client.post(f"/api/v1/ai-interview/session/{token}/submit")
    assert submit.status_code == 200, submit.text

    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    by_q = {a["question_id"]: a for a in detail["answers"]}
    assert by_q["q2"]["answer_text"] == "Saya tetap tenang dan bikin prioritas."
    assert by_q["q1"]["audio_duration_sec"] == 12.5
    link = client.get(
        f"/api/v1/ai-interview/responses/{response_id}/answers/q1/audio-url", headers=admin
    )
    assert link.status_code == 200 and link.json()["channels"] == ["Kandidat"]


def test_recording_silent_answer_blocks_submit_until_rerecorded(client, monkeypatch):
    _, token, _ = _recording_setup(client, monkeypatch, ["", "Jawaban kedua terdengar jelas."])
    _upload(client, token, "q1")
    rec = client.get(f"/api/v1/ai-interview/session/{token}").json()["recorded_answers"]
    assert rec[0]["status"] == "failed"  # transkrip kosong = suara tidak tertangkap
    blocked = client.post(f"/api/v1/ai-interview/session/{token}/submit")
    assert blocked.status_code == 422

    _upload(client, token, "q1")  # rekam ulang
    rec = client.get(f"/api/v1/ai-interview/session/{token}").json()["recorded_answers"]
    assert rec[0]["status"] == "ready" and rec[0]["attempts_used"] == 2


def test_recording_retake_limit_and_old_audio_deleted(client, monkeypatch):
    from app.core.config import get_settings

    admin, token, response_id = _recording_setup(client, monkeypatch, ["a b c"] * 4)
    root = get_settings().uploads_root
    keys = []
    for _ in range(3):
        assert _upload(client, token, "q1").status_code == 202
        detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin)
        keys.append(detail.json()["answers"][0]["audio_object_key"])
    assert len(set(keys)) == 3
    # Rekaman lama terhapus dari storage; hanya yang terakhir tersisa.
    assert not (root / keys[0]).exists() and (root / keys[2]).exists()
    fourth = _upload(client, token, "q1")
    assert fourth.status_code == 409

    # Penarikan persetujuan menghapus file rekaman jawaban juga.
    client.post(f"/api/v1/ai-interview/session/{token}/withdraw-consent")
    assert not (root / keys[2]).exists()


def test_recording_upload_guards(client, monkeypatch):
    from app.core.config import get_settings

    admin, token, _ = _recording_setup(client, monkeypatch, [])
    assert _upload(client, token, "q-tidak-ada").status_code == 404
    assert _upload(client, token, "q1", ctype="text/plain").status_code == 422
    too_long = client.post(
        f"/api/v1/ai-interview/session/{token}/answers/q1/audio?duration_sec=600",
        content=b"x",
        headers={"Content-Type": "audio/webm"},
    )
    assert too_long.status_code == 422
    monkeypatch.setattr(get_settings(), "stt_base_url", None)
    assert _upload(client, token, "q1").status_code == 503

    # Template mode teks menolak unggah rekaman.
    text_tpl = _create_active_template(client, admin)
    cand = _create_candidate(client, admin, name="Eko", email="eko@example.com")
    text_token = _invite(client, admin, text_tpl["id"], cand)["invite_token"]
    monkeypatch.setattr(get_settings(), "stt_base_url", "http://stt.test/v1")
    assert _upload(client, text_token, "q1").status_code == 422


def test_session_polling_does_not_exhaust_rate_limit(client, monkeypatch):
    """Mode rekaman mem-polling status transkripsi; dulu GET sesi berbagi
    batas 30/jam per IP dgn aksi tulis -> kandidat terkena 429 di tengah
    interview setelah ~1 menit menunggu."""
    _, token, _ = _recording_setup(client, monkeypatch, ["a b c"])
    for _ in range(40):
        assert client.get(f"/api/v1/ai-interview/session/{token}").status_code == 200
    assert _upload(client, token, "q1").status_code == 202  # batas tulis terpisah


# ---------- Fase 4 roadmap: alur terstruktur & pedoman percakapan ----------


def test_template_stores_follow_up_settings_and_guidelines(client):
    admin = _auth_header(client)
    payload = _template_payload(mode="realtime_voice")
    payload["questions"][0]["follow_up_max"] = 2
    payload["questions"][0]["follow_up_focus"] = "hasil yang terukur"
    payload["guidelines"] = [
        {"condition": "Kandidat bertanya soal shift", "response": "Shift kerja 3x8 jam."}
    ]
    created = client.post("/api/v1/ai-interview/templates", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["questions"][0]["follow_up_max"] == 2
    assert body["questions"][1]["follow_up_max"] == 1  # default
    assert body["guidelines"][0]["response"] == "Shift kerja 3x8 jam."

    patched = client.patch(
        f"/api/v1/ai-interview/templates/{body['id']}", headers=admin, json={"guidelines": []}
    )
    assert patched.json()["guidelines"] == []


def test_protected_attribute_questions_rejected(client):
    admin = _auth_header(client)
    payload = _template_payload()
    payload["questions"][1]["prompt"] = "Apakah Anda  SUDAH MENIKAH?"
    resp = client.post("/api/v1/ai-interview/templates", headers=admin, json=payload)
    assert resp.status_code == 422
    assert "sudah menikah" in resp.text

    payload = _template_payload()
    payload["guidelines"] = [
        {"condition": "Kandidat diam lama", "response": "Boleh tahu apa agama Anda?"}
    ]
    assert (
        client.post("/api/v1/ai-interview/templates", headers=admin, json=payload).status_code
        == 422
    )

    payload = _template_payload()
    payload["questions"][0]["follow_up_max"] = 5
    assert (
        client.post("/api/v1/ai-interview/templates", headers=admin, json=payload).status_code
        == 422
    )


def test_legacy_template_violating_new_rules_still_readable(client):
    """Validasi kebijakan hanya saat menyimpan: template lama yang tersimpan
    sebelum aturan baru tidak boleh membuat daftar template error 500."""
    from uuid import UUID

    from app.modules.ai_interview.models import AIInterviewTemplate

    admin = _auth_header(client)
    template = _create_active_template(client, admin)
    db = client.testing_session()
    row = db.get(AIInterviewTemplate, UUID(template["id"]))
    row.questions_json = '[{"id": "q1", "prompt": "Apa agama Anda?"}]'
    row.criteria_json = '[{"key": "nada", "label": "Nada suara"}]'
    db.commit()
    db.close()
    listed = client.get("/api/v1/ai-interview/templates", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["questions"][0]["prompt"] == "Apa agama Anda?"


def test_voice_context_sends_builtin_then_template_guidelines(client, monkeypatch):
    admin = _auth_header(client)
    payload_guidelines = [
        {"condition": "Kandidat bertanya soal gaji", "response": "Kisaran gaji 5-6 juta."}
    ]
    template = _create_active_template(
        client, admin, mode="realtime_voice", guidelines=payload_guidelines
    )
    cand_id = _create_candidate(client, admin)
    token = _invite(client, admin, template["id"], cand_id)["invite_token"]
    ctx = client.get(
        f"/api/v1/ai-interview/session/{token}/voice/context",
        headers=_agent_headers(monkeypatch, token),
    ).json()
    guidelines = ctx["guidelines"]
    keys = [g["key"] for g in guidelines if g["source"] == "sistem"]
    assert keys[:3] == ["atribut_dilindungi", "hasil_penilaian", "manipulasi"]
    assert all(g["locked"] for g in guidelines[:3])
    assert guidelines[-1] == {
        "key": None,
        "condition": "Kandidat bertanya soal gaji",
        "response": "Kisaran gaji 5-6 juta.",
        "locked": False,
        "source": "template",
    }
    assert ctx["questions"][0]["follow_up_max"] == 1

    # Pedoman template tidak pernah bocor ke kandidat.
    session = client.get(f"/api/v1/ai-interview/session/{token}").json()
    assert "guidelines" not in session and "Kisaran gaji" not in str(session)


def test_builtin_guidelines_listed_for_staff(client):
    admin = _auth_header(client)
    resp = client.get("/api/v1/ai-interview/guidelines/builtin", headers=admin)
    assert resp.status_code == 200
    locked = [g["key"] for g in resp.json() if g["locked"]]
    assert "atribut_dilindungi" in locked
    assert client.get("/api/v1/ai-interview/guidelines/builtin").status_code == 401


def test_marker_lines_never_count_as_candidate_evidence():
    from app.modules.ai_interview.service import _candidate_lines

    transcript = (
        "## Pertanyaan 1: Ceritakan pengalaman menangani komplain pelanggan\n"
        "Pewawancara AI: Ceritakan pengalaman menangani komplain pelanggan.\n"
        "Kandidat: Saya dengarkan keluhan pelanggan dulu."
    )
    lines = _candidate_lines(transcript)
    assert "menangani komplain" not in lines
    assert "dengarkan keluhan" in lines


# ---------- Fase 5 roadmap: bukti bertimestamp, konsistensi skor, pipeline ----------


def _fake_scoring(monkeypatch, runs: list[dict[str, tuple[int, list[str]]]]):
    """Mock LLM penilai: tiap panggilan mengambil run berikutnya
    {criterion_key: (skor, [kutipan])}; run terakhir dipakai berulang."""
    from app.modules.ai_interview import service as svc

    queue = list(runs)

    def fake(system, user, **kwargs):
        run = queue.pop(0) if len(queue) > 1 else queue[0]
        return {
            "narrative": "Ringkasan.",
            "breakdown": [
                {"criterion_key": k, "score": sc, "reasoning": "alasan", "evidence": ev}
                for k, (sc, ev) in run.items()
            ],
        }

    monkeypatch.setattr(svc, "chat_completion", fake)


def test_locate_evidence_maps_quote_to_answer_and_second():
    from app.modules.ai_interview.service import locate_evidence

    answers = [
        {"question_id": "q1", "answer_text": "Halo semua."},
        {
            "question_id": "q2",
            "answer_text": "Saya kerja di call-center, lalu refund pelanggan.",
            "words": [
                [0.0, 0.3, "Saya"],
                [0.3, 0.6, "kerja"],
                [0.6, 0.8, "di"],
                [0.8, 1.5, "call-center,"],
                [1.6, 2.0, "lalu"],
                [2.0, 2.5, "refund"],
            ],
        },
    ]
    # "call-center," dinormalisasi jadi 2 token; kutipan mulai di tengahnya.
    ref = locate_evidence("center, lalu refund", answers)
    assert ref == {"quote": "center, lalu refund", "question_id": "q2", "start": 0.8}
    # Jawaban teks (tanpa words): hanya pertanyaannya yang diketahui.
    assert locate_evidence("Halo semua", answers)["start"] is None
    # Kalimat sama di 2 jawaban: pertanyaan terkait kriteria didahulukan
    # (ditemukan saat uji live -- dulu selalu jatuh ke jawaban pertama).
    dup = [
        {"question_id": "q1", "answer_text": "a b c"},
        {"question_id": "q2", "answer_text": "a b c"},
    ]
    assert locate_evidence("a b c", dup)["question_id"] == "q1"
    assert locate_evidence("a b c", dup, {"q2"})["question_id"] == "q2"
    assert locate_evidence("tidak ada di jawaban", answers)["question_id"] is None


def test_merge_runs_averages_and_flags_unstable():
    from app.modules.ai_interview.service import merge_scoring_runs

    criteria = [{"key": "a", "weight": 1}, {"key": "b", "weight": 1}, {"key": "c", "weight": 1}]

    def item(key, score, supported, evidence=()):
        return {
            "criterion_key": key,
            "weight": 1.0,
            "score": score,
            "reasoning": "",
            "evidence": list(evidence),
            "dropped_quotes": 0,
            "supported": supported,
        }

    run1 = [item("a", 90, True, ["x y z"]), item("b", 70, True, ["p q r"]), item("c", 50, True)]
    run2 = [item("a", 60, True, ["x y z", "u v w"]), item("b", 74, True), item("c", 40, False)]
    merged, overall = merge_scoring_runs([run1, run2], criteria)
    a, b, c = merged
    assert (a["score"], a["stable"], a["score_runs"]) == (75, False, [90, 60])
    assert a["evidence"] == ["x y z", "u v w"]
    assert (b["score"], b["stable"]) == (72, True)
    # Satu run menemukan bukti, run lain tidak -> tidak stabil.
    assert (c["score"], c["supported"], c["stable"]) == (50, True, False)
    assert overall == round((75 + 72 + 50) / 3)


def test_recording_scored_with_evidence_timestamps(client, monkeypatch):
    admin, token, response_id = _recording_setup(
        client,
        monkeypatch,
        [
            "Saya selalu mendengarkan keluhan pelanggan dulu",
            "Saya urutkan antrean berdasarkan urgensi",
        ],
    )
    _fake_scoring(
        monkeypatch,
        [
            {
                "komunikasi": (80, ["mendengarkan keluhan pelanggan"]),
                "ketahanan": (70, ["antrean berdasarkan urgensi"]),
            }
        ],
    )
    assert _upload(client, token, "q1").status_code == 202
    assert _upload(client, token, "q2").status_code == 202
    assert client.post(f"/api/v1/ai-interview/session/{token}/submit").status_code == 200

    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert detail["status"] == "dinilai"
    by_key = {b["criterion_key"]: b for b in detail["ai_score_breakdown"]}
    assert by_key["komunikasi"]["evidence_refs"] == [
        {"quote": "mendengarkan keluhan pelanggan", "question_id": "q1", "start": 1.0}
    ]
    assert by_key["ketahanan"]["evidence_refs"][0]["question_id"] == "q2"
    # Dua run identik -> stabil.
    assert by_key["komunikasi"]["score_runs"] == [80, 80] and by_key["komunikasi"]["stable"]


def test_unstable_scoring_visible_in_calibration(client, monkeypatch):
    admin = _auth_header(client)
    _fake_scoring(
        monkeypatch,
        [
            {"komunikasi": (90, ["Jawaban pribadi kandidat"])},
            {"komunikasi": (50, ["Jawaban pribadi kandidat"])},
        ],
    )
    _, response_id = _submit_text_interview(client, admin)
    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    kom = next(b for b in detail["ai_score_breakdown"] if b["criterion_key"] == "komunikasi")
    assert (kom["score"], kom["stable"]) == (70, False)

    # Reviewer menyesuaikan skor -> skor AI asli tersimpan untuk kalibrasi.
    reviewed = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disesuaikan", "ai_score_overall": 55},
    ).json()
    assert (reviewed["ai_score_original"], reviewed["ai_score_overall"]) == (70, 55)
    calib = client.get(
        f"/api/v1/ai-interview/templates/{detail['template_id']}/calibration", headers=admin
    ).json()
    assert calib == {
        "scored": 1,
        "reviewed": 1,
        "approved": 0,
        "adjusted": 1,
        "rejected": 0,
        "mean_adjustment": 15.0,
        "unstable": 1,
    }


def test_single_scoring_run_when_consistency_disabled(client, monkeypatch):
    from app.core.config import get_settings
    from app.modules.ai_interview import service as svc

    monkeypatch.setattr(get_settings(), "ai_interview_scoring_runs", 1)
    calls = []

    def fake(system, user, **kwargs):
        calls.append(1)
        return {"breakdown": [{"criterion_key": "komunikasi", "score": 60, "evidence": []}]}

    monkeypatch.setattr(svc, "chat_completion", fake)
    admin = _auth_header(client)
    _submit_text_interview(client, admin)
    assert len(calls) == 1


def test_review_can_move_candidate_in_pipeline(client, monkeypatch):
    admin = _auth_header(client)
    _fake_scoring(monkeypatch, [{"komunikasi": (80, ["Jawaban pribadi kandidat"])}])
    client_id = _client_id(client, admin)
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={"client_id": client_id, "title": "CS", "headcount": 1},
    )
    assert jo.status_code == 201, jo.text
    jo_id = jo.json()["id"]
    template = _create_active_template(client, admin, job_order_id=jo_id)
    cand_id = _create_candidate(client, admin, name="Tono", email="tono@example.com")
    invited = _invite(client, admin, template["id"], cand_id)
    token, response_id = invited["invite_token"], invited["response_id"]
    client.post(f"/api/v1/ai-interview/session/{token}/start")
    client.post(
        f"/api/v1/ai-interview/session/{token}/answer",
        json={"question_id": "q1", "answer_text": "Jawaban pribadi kandidat"},
    )
    client.post(f"/api/v1/ai-interview/session/{token}/submit")

    # Belum ada di pipeline JO -> aksi pipeline ditolak, review tidak tersimpan.
    no_pipeline = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disetujui", "placement_status": "disubmit"},
    )
    assert no_pipeline.status_code == 422
    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin).json()
    assert detail["review_status"] == "menunggu_review" and detail["placement_id"] is None

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=admin,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    ).json()
    listed = client.get(
        f"/api/v1/ai-interview/responses?template_id={template['id']}", headers=admin
    ).json()
    assert listed[0]["placement_status"] == "disourcing"

    # Tahap di luar daftar yang diizinkan ditolak (offering punya alur sendiri).
    bad = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disetujui", "placement_status": "offering"},
    )
    assert bad.status_code == 422

    ok = client.post(
        f"/api/v1/ai-interview/responses/{response_id}/review",
        headers=admin,
        json={"review_status": "disetujui", "placement_status": "gagal"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["placement_status"] == "gagal"
    moved = client.get("/api/v1/recruitment/placements", headers=admin).json()
    row = next(p for p in moved if p["id"] == placement["id"])
    assert row["status"] == "gagal"
    assert row["rejection_note"] == "Tidak lolos tahap AI Interview"
