"""AI Interview (PRD v3.1 Patch 4) — service layer.

Sisi staf (authenticated, RBAC) dan sisi kandidat (publik via `invite_token`,
tanpa akun — kandidat AEOS tidak pernah punya akun `User`) hidup di modul
yang sama tapi lewat jalur berbeda. Konteks tenant untuk sisi kandidat
mengikuti pola persis `job_portal/service.py::get_application_status()`:
`AIInterviewResponse` dicari dulu unscoped by `invite_token` (unique global),
baru `set_tenant()` sebelum load data terkait lain, dibungkus try/finally.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.database import parse_uuid
from app.core.llm import chat_completion
from app.core.tenancy import get_tenant, set_tenant
from app.modules import audit
from app.modules.ai_interview.models import (
    AIInterviewMode,
    AIInterviewResponse,
    AIInterviewResponseStatus,
    AIInterviewReviewStatus,
    AIInterviewTemplate,
    AIInterviewTemplateStatus,
)
from app.modules.ai_interview.schemas import (
    AIInterviewInviteIn,
    AIInterviewInviteOut,
    AIInterviewInviteResultItem,
    AIInterviewReviewIn,
    AIInterviewTemplateCreate,
    AIInterviewTemplateUpdate,
    AnswerIn,
    InterviewCriterionIn,
    PublicInterviewQuestionOut,
    PublicInterviewSessionOut,
    VoiceContextOut,
    VoiceContextQuestionOut,
    VoiceSessionOut,
)
from app.modules.notifications.service import send_raw_email
from app.modules.recruitment.models import Candidate
from fastapi import HTTPException
from livekit import api as lk_api
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Harus sama persis dengan `agent_name` yang didaftarkan worker `agent/`
# (lihat `agent/main.py`) -- LiveKit mencocokkan dispatch eksplisit by name.
_VOICE_AGENT_NAME = "ai-interview-agent"

_SCORE_SYSTEM_PROMPT = (
    "Anda asisten rekrutmen AI. Nilai jawaban kandidat interview berdasarkan "
    "kriteria yang diberikan. Untuk TIAP kriteria, beri skor 0-100 dan alasan "
    "singkat berbasis jawaban yang benar-benar ada (jangan mengarang). Beri "
    "juga skor keseluruhan 0-100 dan narasi ringkas 2-3 kalimat Bahasa "
    "Indonesia. Balas HANYA JSON sesuai skema:\n"
    "{\n"
    '  "overall": number,\n'
    '  "narrative": string,\n'
    '  "breakdown": [{"criterion_key": string, "score": number, "reasoning": string}]\n'
    "}"
)


# ---------- Sisi staf: template ----------


def _get_template_or_404(db: Session, template_id: str) -> AIInterviewTemplate:
    template = db.get(AIInterviewTemplate, parse_uuid(template_id))
    if template is None:
        raise HTTPException(status_code=404, detail="Template AI Interview tidak ditemukan")
    return template


def create_template(db: Session, payload: AIInterviewTemplateCreate, user) -> AIInterviewTemplate:
    template = AIInterviewTemplate(
        job_order_id=payload.job_order_id,
        title=payload.title,
        objective=payload.objective,
        mode=payload.mode,
        questions_json=json.dumps([q.model_dump() for q in payload.questions], ensure_ascii=False),
        criteria_json=json.dumps([c.model_dump() for c in payload.criteria], ensure_ascii=False),
        created_by=getattr(user, "id", None),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def list_templates(
    db: Session, job_order_id: str | None = None, status: AIInterviewTemplateStatus | None = None
) -> list[AIInterviewTemplate]:
    stmt = select(AIInterviewTemplate).order_by(AIInterviewTemplate.created_at.desc())
    if job_order_id is not None:
        stmt = stmt.where(AIInterviewTemplate.job_order_id == parse_uuid(job_order_id))
    if status is not None:
        stmt = stmt.where(AIInterviewTemplate.status == status)
    return list(db.execute(stmt).scalars())


def get_template(db: Session, template_id: str) -> AIInterviewTemplate:
    return _get_template_or_404(db, template_id)


def update_template(
    db: Session, template_id: str, payload: AIInterviewTemplateUpdate
) -> AIInterviewTemplate:
    template = _get_template_or_404(db, template_id)
    data = payload.model_dump(exclude_unset=True)
    if "questions" in data:
        questions = data.pop("questions")
        template.questions_json = json.dumps(questions or [], ensure_ascii=False)
    if "criteria" in data:
        criteria = data.pop("criteria")
        template.criteria_json = json.dumps(criteria or [], ensure_ascii=False)
    for field, value in data.items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


# ---------- Sisi staf: undang kandidat ----------


def invite_candidates(
    db: Session, template_id: str, payload: AIInterviewInviteIn, user
) -> AIInterviewInviteOut:
    template = _get_template_or_404(db, template_id)
    if template.status != AIInterviewTemplateStatus.active:
        raise HTTPException(
            status_code=422,
            detail="Template harus berstatus aktif sebelum bisa dipakai mengundang kandidat",
        )

    settings = get_settings()
    base_url = (settings.cors_origin_list[0] if settings.cors_origin_list else "").rstrip("/")

    invited: list[AIInterviewInviteResultItem] = []
    skipped: list[dict] = []
    for candidate_id in payload.candidate_ids:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None:
            skipped.append(
                {"candidate_id": str(candidate_id), "reason": "Kandidat tidak ditemukan"}
            )
            continue
        token = secrets.token_urlsafe(32)
        response = AIInterviewResponse(
            template_id=template.id,
            candidate_id=candidate.id,
            job_order_id=template.job_order_id,
            invite_token=token,
            expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
        )
        db.add(response)
        db.flush()

        email_sent = False
        if candidate.email:
            link = f"{base_url}/ai-interview/session/{token}"
            expires_label = (
                response.expires_at.strftime("%d %B %Y %H:%M") if response.expires_at else "-"
            )
            send_raw_email(
                candidate.email,
                f"Undangan Interview AI — {template.title}",
                f"Halo {candidate.full_name},\n\n"
                f"Anda diundang mengikuti interview untuk posisi terkait {template.title}. "
                f"Silakan buka link berikut untuk mulai:\n{link}\n\n"
                f"Link ini berlaku sampai {expires_label}.",
            )
            email_sent = True

        invited.append(
            AIInterviewInviteResultItem(
                candidate_id=candidate.id,
                response_id=response.id,
                invite_token=token,
                email_sent=email_sent,
            )
        )

    db.commit()
    audit.log_event(
        db,
        action="ai_interview.invited",
        entity_type="ai_interview_template",
        entity_id=template.id,
        detail={
            "invited": len(invited),
            "skipped": len(skipped),
            "by": getattr(user, "email", "?"),
        },
    )
    return AIInterviewInviteOut(invited=invited, skipped=skipped)


# ---------- Sisi staf: response & review ----------


def _get_response_or_404(db: Session, response_id: str) -> AIInterviewResponse:
    response = db.get(AIInterviewResponse, parse_uuid(response_id))
    if response is None:
        raise HTTPException(status_code=404, detail="Response AI Interview tidak ditemukan")
    return response


def list_responses(
    db: Session,
    template_id: str | None = None,
    candidate_id: str | None = None,
    job_order_id: str | None = None,
    status: AIInterviewResponseStatus | None = None,
    review_status: AIInterviewReviewStatus | None = None,
) -> list[AIInterviewResponse]:
    stmt = select(AIInterviewResponse).order_by(AIInterviewResponse.invited_at.desc())
    if template_id is not None:
        stmt = stmt.where(AIInterviewResponse.template_id == parse_uuid(template_id))
    if candidate_id is not None:
        stmt = stmt.where(AIInterviewResponse.candidate_id == parse_uuid(candidate_id))
    if job_order_id is not None:
        stmt = stmt.where(AIInterviewResponse.job_order_id == parse_uuid(job_order_id))
    if status is not None:
        stmt = stmt.where(AIInterviewResponse.status == status)
    if review_status is not None:
        stmt = stmt.where(AIInterviewResponse.review_status == review_status)
    return list(db.execute(stmt).scalars())


def get_response(db: Session, response_id: str) -> AIInterviewResponse:
    return _get_response_or_404(db, response_id)


def resend_invite(db: Session, response_id: str) -> AIInterviewResponse:
    response = _get_response_or_404(db, response_id)
    if response.status in (AIInterviewResponseStatus.submitted, AIInterviewResponseStatus.scored):
        raise HTTPException(status_code=422, detail="Interview ini sudah diselesaikan kandidat")
    template = db.get(AIInterviewTemplate, response.template_id)
    candidate = db.get(Candidate, response.candidate_id)

    response.invite_token = secrets.token_urlsafe(32)
    response.expires_at = datetime.now(UTC) + timedelta(hours=72)
    if response.status == AIInterviewResponseStatus.expired:
        response.status = AIInterviewResponseStatus.invited
    db.commit()
    db.refresh(response)

    if candidate and candidate.email and template:
        settings = get_settings()
        base_url = (settings.cors_origin_list[0] if settings.cors_origin_list else "").rstrip("/")
        link = f"{base_url}/ai-interview/session/{response.invite_token}"
        send_raw_email(
            candidate.email,
            f"Undangan Interview AI — {template.title}",
            f"Halo {candidate.full_name},\n\nLink interview Anda diperbarui:\n{link}",
        )
    return response


def score_response(db: Session, response_id: str) -> AIInterviewResponse:
    response = _get_response_or_404(db, response_id)
    if response.status not in (
        AIInterviewResponseStatus.submitted,
        AIInterviewResponseStatus.scored,
    ):
        raise HTTPException(
            status_code=422, detail="Interview belum disubmit kandidat — belum ada yang dinilai"
        )
    template = db.get(AIInterviewTemplate, response.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template terkait tidak ditemukan")
    if not _score(db, response, template):
        raise HTTPException(
            status_code=503, detail="Fitur AI belum aktif atau gagal menilai. Coba lagi nanti."
        )
    return response


def review_response(
    db: Session, user, response_id: str, payload: AIInterviewReviewIn
) -> AIInterviewResponse:
    response = _get_response_or_404(db, response_id)
    if response.status not in (
        AIInterviewResponseStatus.submitted,
        AIInterviewResponseStatus.scored,
    ):
        raise HTTPException(
            status_code=422, detail="Interview belum disubmit kandidat — belum bisa direview"
        )

    response.review_status = payload.review_status
    response.review_notes = (payload.review_notes or "").strip()[:2000] or None
    response.reviewed_by = getattr(user, "id", None)
    response.reviewed_at = datetime.now(UTC)
    if payload.review_status == AIInterviewReviewStatus.adjusted:
        if payload.ai_score_overall is not None:
            response.ai_score_overall = max(0, min(100, payload.ai_score_overall))
        if payload.ai_score_breakdown is not None:
            response.ai_score_breakdown_json = json.dumps(
                payload.ai_score_breakdown, ensure_ascii=False
            )
    db.commit()
    db.refresh(response)
    audit.log_event(
        db,
        action="ai_interview.reviewed",
        entity_type="ai_interview_response",
        entity_id=response.id,
        detail={"review_status": payload.review_status.value, "by": getattr(user, "email", "?")},
    )
    return response


# ---------- Skoring AI (dipakai submit otomatis & trigger manual) ----------


def _score(db: Session, response: AIInterviewResponse, template: AIInterviewTemplate) -> bool:
    """Kembalikan True kalau berhasil dinilai & sudah commit; False kalau AI
    gagal/tidak aktif (TIDAK melempar — caller putuskan apa yang terjadi
    kalau gagal, konsisten prinsip "AI gagal tidak boleh mematahkan alur")."""
    answers_by_q = {a.get("question_id"): a.get("answer_text", "") for a in response.answers}
    qa_pairs = [
        {
            "question_id": q.get("id"),
            "prompt": q.get("prompt"),
            "criterion_keys": q.get("criterion_keys", []),
            "answer": answers_by_q.get(q.get("id"), ""),
        }
        for q in template.questions
    ]
    user_payload = {"criteria": template.criteria, "qa": qa_pairs}
    return _run_scoring(db, response, user_payload)


def _score_transcript(
    db: Session, response: AIInterviewResponse, template: AIInterviewTemplate, transcript: str
) -> bool:
    """Varian `_score()` untuk mode `realtime_voice` — satu transkrip
    percakapan utuh dinilai holistik terhadap kriteria, bukan pasangan
    per-pertanyaan (agent tidak menjamin urutan/cakupan pertanyaan kaku)."""
    topics = [
        {"prompt": q.get("prompt"), "criterion_keys": q.get("criterion_keys", [])}
        for q in template.questions
    ]
    user_payload = {"criteria": template.criteria, "topics": topics, "transcript": transcript}
    return _run_scoring(db, response, user_payload)


def _run_scoring(db: Session, response: AIInterviewResponse, user_payload: dict) -> bool:
    try:
        result = chat_completion(
            _SCORE_SYSTEM_PROMPT,
            json.dumps(user_payload, ensure_ascii=False),
            feature="ai_interview.score",
        )
    except Exception:  # noqa: BLE001 - AI gagal → biarkan status apa adanya, jangan crash
        logger.warning("Scoring AI Interview gagal untuk response %s", response.id, exc_info=True)
        return False
    if not isinstance(result, dict):
        return False

    try:
        overall = max(0, min(100, int(result.get("overall", 0))))
    except (TypeError, ValueError):
        overall = 0
    breakdown_raw = result.get("breakdown")
    breakdown = breakdown_raw if isinstance(breakdown_raw, list) else []
    narrative = str(result.get("narrative") or "").strip()[:2000] or None

    response.ai_score_overall = overall
    response.ai_score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
    response.ai_narrative = narrative
    response.ai_model = get_settings().ai_model
    response.status = AIInterviewResponseStatus.scored
    db.commit()
    db.refresh(response)
    audit.log_event(
        db,
        action="ai_interview.scored",
        entity_type="ai_interview_response",
        entity_id=response.id,
        detail={"overall": overall},
    )
    return True


# ---------- Sisi kandidat: publik via invite_token ----------


def _resolve_response_by_token(db: Session, token: str) -> AIInterviewResponse:
    response = db.execute(
        select(AIInterviewResponse).where(AIInterviewResponse.invite_token == token)
    ).scalar_one_or_none()
    if response is None:
        raise HTTPException(status_code=404, detail="Token interview tidak ditemukan")

    # SQLite (dev/test) tidak mempertahankan tzinfo pada DateTime(timezone=True)
    # -- ternormalisasi UTC dulu sebelum dibandingkan (pola sama seperti
    # `core/ratelimit.py::SlidingWindowLimiter.check`).
    expires_at = response.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    _not_yet_done = (AIInterviewResponseStatus.invited, AIInterviewResponseStatus.in_progress)
    if expires_at and expires_at < datetime.now(UTC) and response.status in _not_yet_done:
        response.status = AIInterviewResponseStatus.expired
        db.commit()

    if response.status == AIInterviewResponseStatus.expired:
        raise HTTPException(status_code=410, detail="Link interview ini sudah kedaluwarsa")

    set_tenant(response.tenant_id)
    return response


def get_session(db: Session, token: str) -> PublicInterviewSessionOut:
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        template = db.get(AIInterviewTemplate, response.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template interview tidak ditemukan")
        questions = [
            PublicInterviewQuestionOut(
                id=q.get("id", ""),
                order=q.get("order", 1),
                type=q.get("type", "open_ended"),
                prompt=q.get("prompt", ""),
                options=q.get("options"),
            )
            for q in sorted(template.questions, key=lambda q: q.get("order", 1))
        ]
        return PublicInterviewSessionOut(
            title=template.title,
            objective=template.objective,
            status=response.status,
            mode=template.mode,
            questions=questions,
            expires_at=response.expires_at,
        )
    finally:
        set_tenant(prev_tenant)


def start_session(db: Session, token: str) -> None:
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        if response.status == AIInterviewResponseStatus.invited:
            response.status = AIInterviewResponseStatus.in_progress
            response.started_at = datetime.now(UTC)
            db.commit()
    finally:
        set_tenant(prev_tenant)


def submit_answer(db: Session, token: str, payload: AnswerIn) -> None:
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        if response.status not in (
            AIInterviewResponseStatus.invited,
            AIInterviewResponseStatus.in_progress,
        ):
            raise HTTPException(status_code=422, detail="Interview ini sudah disubmit")
        if response.status == AIInterviewResponseStatus.invited:
            response.status = AIInterviewResponseStatus.in_progress
            response.started_at = response.started_at or datetime.now(UTC)

        answers = response.answers
        answers = [a for a in answers if a.get("question_id") != payload.question_id]
        answers.append(
            {
                "question_id": payload.question_id,
                "answer_text": payload.answer_text.strip()[:8000],
                "submitted_at": datetime.now(UTC).isoformat(),
            }
        )
        response.answers_json = json.dumps(answers, ensure_ascii=False)
        db.commit()
    finally:
        set_tenant(prev_tenant)


def submit_session(db: Session, token: str) -> AIInterviewResponse:
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        if response.status not in (
            AIInterviewResponseStatus.invited,
            AIInterviewResponseStatus.in_progress,
        ):
            raise HTTPException(status_code=422, detail="Interview ini sudah disubmit sebelumnya")
        if not response.answers:
            raise HTTPException(status_code=422, detail="Belum ada jawaban yang diisi")

        response.status = AIInterviewResponseStatus.submitted
        response.submitted_at = datetime.now(UTC)
        db.commit()
        db.refresh(response)
        audit.log_event(
            db,
            action="ai_interview.submitted",
            entity_type="ai_interview_response",
            entity_id=response.id,
            detail={"candidate_id": str(response.candidate_id)},
        )

        template = db.get(AIInterviewTemplate, response.template_id)
        if template is not None:
            _score(db, response, template)  # best-effort — status tetap "submitted" kalau gagal
        return response
    finally:
        set_tenant(prev_tenant)


# ---------- AI Interview Fase 2: percakapan suara real-time, self-hosted ----------
#
# LLM/reasoning TETAP lewat chat_completion() di atas (AI_BASE_URL yang sama) --
# self-hosted di sini cuma STT+TTS (dikonfigurasi di agent worker `agent/`,
# bukan di sini). Backend TIDAK menjalankan pipeline suara — cuma mint
# kredensial LiveKit + dispatch agent + jadi jembatan REST agar agent tidak
# perlu akses DB/tenant-context langsung (lihat catatan desain di plan file).


async def start_voice_session(db: Session, token: str) -> VoiceSessionOut:
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        if response.status not in (
            AIInterviewResponseStatus.invited,
            AIInterviewResponseStatus.in_progress,
        ):
            raise HTTPException(status_code=422, detail="Interview ini sudah disubmit sebelumnya")

        template = db.get(AIInterviewTemplate, response.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template interview tidak ditemukan")
        if template.mode != AIInterviewMode.realtime_voice:
            raise HTTPException(status_code=422, detail="Template ini bukan mode percakapan suara")

        settings = get_settings()
        if not settings.voice_interview_configured:
            raise HTTPException(
                status_code=503,
                detail="Fitur interview suara belum aktif (LIVEKIT_* belum dikonfigurasi).",
            )

        candidate = db.get(Candidate, response.candidate_id)
        identity = str(response.candidate_id)
        display_name = candidate.full_name if candidate else "Kandidat"
        room_name = f"ai-interview-{response.id}"

        access_token = (
            lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(identity)
            .with_name(display_name)
            .with_grants(lk_api.VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )

        # Dispatch eksplisit (bukan auto-dispatch) supaya agent hanya join room
        # yang benar-benar sudah diverifikasi (token valid, template aktif,
        # infra terkonfigurasi) -- bukan tiap room yang tercipta di LiveKit.
        # `metadata=token` meneruskan invite_token ke agent lewat job metadata
        # (agent panggil balik `GET .../voice/context` pakai token yang sama,
        # kredensial yang sama seperti kandidat -- lihat get_voice_context()).
        async with lk_api.LiveKitAPI(
            settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
        ) as lkapi:
            await lkapi.agent_dispatch.create_dispatch(
                lk_api.CreateAgentDispatchRequest(
                    room=room_name, agent_name=_VOICE_AGENT_NAME, metadata=token
                )
            )

        if response.status == AIInterviewResponseStatus.invited:
            response.status = AIInterviewResponseStatus.in_progress
            response.started_at = response.started_at or datetime.now(UTC)
            db.commit()

        return VoiceSessionOut(url=settings.livekit_url or "", token=access_token)
    finally:
        set_tenant(prev_tenant)


def get_voice_context(db: Session, token: str) -> VoiceContextOut:
    """Dipanggil agent worker (BUKAN browser kandidat) — kredensial
    `invite_token` yang sama, tapi boleh balikin `criterion_keys` karena
    konsumennya bukan kandidat (beda dari `get_session()`/
    `PublicInterviewSessionOut` yang sengaja menyembunyikan itu)."""
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        template = db.get(AIInterviewTemplate, response.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template interview tidak ditemukan")
        questions = [
            VoiceContextQuestionOut(
                id=q.get("id", ""),
                order=q.get("order", 1),
                prompt=q.get("prompt", ""),
                criterion_keys=q.get("criterion_keys", []),
            )
            for q in sorted(template.questions, key=lambda q: q.get("order", 1))
        ]
        criteria = [InterviewCriterionIn(**c) for c in template.criteria]
        return VoiceContextOut(
            title=template.title,
            objective=template.objective,
            questions=questions,
            criteria=criteria,
        )
    finally:
        set_tenant(prev_tenant)


def complete_voice_session(db: Session, token: str, transcript: str) -> AIInterviewResponse:
    """Dipanggil agent worker saat percakapan selesai — mirror `submit_session()`
    tapi menerima transkrip percakapan penuh, bukan jawaban per-pertanyaan."""
    prev_tenant = get_tenant()
    try:
        response = _resolve_response_by_token(db, token)
        if response.status not in (
            AIInterviewResponseStatus.invited,
            AIInterviewResponseStatus.in_progress,
        ):
            raise HTTPException(status_code=422, detail="Interview ini sudah disubmit sebelumnya")

        response.transcript_text = transcript.strip()[:20000] or None
        response.status = AIInterviewResponseStatus.submitted
        response.submitted_at = datetime.now(UTC)
        db.commit()
        db.refresh(response)
        audit.log_event(
            db,
            action="ai_interview.submitted",
            entity_type="ai_interview_response",
            entity_id=response.id,
            detail={"candidate_id": str(response.candidate_id), "mode": "realtime_voice"},
        )

        template = db.get(AIInterviewTemplate, response.template_id)
        if template is not None and response.transcript_text:
            _score_transcript(db, response, template, response.transcript_text)
        return response
    finally:
        set_tenant(prev_tenant)
