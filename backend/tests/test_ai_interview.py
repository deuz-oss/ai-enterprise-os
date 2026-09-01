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


def _invite(client, headers, template_id, candidate_id) -> dict:
    invite = client.post(
        f"/api/v1/ai-interview/templates/{template_id}/invite",
        headers=headers,
        json={"candidate_ids": [candidate_id]},
    )
    assert invite.status_code == 200, invite.text
    return invite.json()["invited"][0]


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
    monkeypatch.setattr(settings, "tts_base_url", "http://tts.test")

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


def test_voice_context_includes_criterion_keys_unlike_public_session(client):
    admin = _auth_header(client)
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin)
    invited = _invite(client, admin, template["id"], cand_id)
    token = invited["invite_token"]

    ctx = client.get(f"/api/v1/ai-interview/session/{token}/voice/context")
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
                                '{"overall": 77, "narrative": "Cukup baik.", '
                                '"breakdown": [{"criterion_key": "komunikasi", '
                                '"score": 77, "reasoning": "Jelas."}]}'
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

    complete = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
        json={"transcript": "Pewawancara: Ceritakan pengalaman Anda...\nKandidat: Saya pernah..."},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "dinilai"

    detail = client.get(f"/api/v1/ai-interview/responses/{response_id}", headers=admin)
    body = detail.json()
    assert body["status"] == "dinilai"
    assert body["ai_score_overall"] == 77
    assert body["review_status"] == "menunggu_review"
    assert body["transcript_text"] is not None

    # Sudah submit -- panggil complete lagi ditolak (pola sama submit_session()).
    again = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
        json={"transcript": "percakapan lain"},
    )
    assert again.status_code == 422
