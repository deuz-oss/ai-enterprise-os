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

    complete = client.post(
        f"/api/v1/ai-interview/session/{token}/voice/complete",
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
