"""Router AI Interview (PRD v3.1 Patch 4). Dua router terpisah:
`router` (staf, authenticated + RBAC, di-mount dengan guard lisensi
`recruitment` di `main.py`) dan `public_router` (kandidat via `invite_token`,
tanpa autentikasi sama sekali — mirror `payroll/router.py::public_router`)."""

from app.core.database import get_db
from app.core.permissions import RECRUITMENT_ROLES
from app.core.ratelimit import get_limiter
from app.core.security import get_current_user, require_roles
from app.core.tenancy import get_request_meta
from app.modules.ai_interview import service
from app.modules.ai_interview.models import (
    AIInterviewResponseStatus,
    AIInterviewReviewStatus,
    AIInterviewTemplateStatus,
)
from app.modules.ai_interview.schemas import (
    AIInterviewInviteIn,
    AIInterviewInviteOut,
    AIInterviewResponseOut,
    AIInterviewReviewIn,
    AIInterviewTemplateCreate,
    AIInterviewTemplateOut,
    AIInterviewTemplateUpdate,
    AnswerIn,
    PublicInterviewSessionOut,
    VoiceCompleteIn,
    VoiceContextOut,
    VoiceSessionOut,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/ai-interview",
    tags=["ai-interview"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*RECRUITMENT_ROLES))],
)


@router.post(
    "/templates", response_model=AIInterviewTemplateOut, status_code=status.HTTP_201_CREATED
)
def create_template(
    payload: AIInterviewTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.create_template(db, payload, user)


@router.get("/templates", response_model=list[AIInterviewTemplateOut])
def list_templates(
    job_order_id: str | None = Query(None),
    status_filter: AIInterviewTemplateStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return service.list_templates(db, job_order_id=job_order_id, status=status_filter)


@router.get("/templates/{template_id}", response_model=AIInterviewTemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db)):
    return service.get_template(db, template_id)


@router.patch("/templates/{template_id}", response_model=AIInterviewTemplateOut)
def update_template(
    template_id: str, payload: AIInterviewTemplateUpdate, db: Session = Depends(get_db)
):
    return service.update_template(db, template_id, payload)


@router.post("/templates/{template_id}/invite", response_model=AIInterviewInviteOut)
def invite_candidates(
    template_id: str,
    payload: AIInterviewInviteIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.invite_candidates(db, template_id, payload, user)


@router.get("/responses", response_model=list[AIInterviewResponseOut])
def list_responses(
    template_id: str | None = Query(None),
    candidate_id: str | None = Query(None),
    job_order_id: str | None = Query(None),
    status_filter: AIInterviewResponseStatus | None = Query(None, alias="status"),
    review_status: AIInterviewReviewStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.list_responses(
        db,
        template_id=template_id,
        candidate_id=candidate_id,
        job_order_id=job_order_id,
        status=status_filter,
        review_status=review_status,
    )


@router.get("/responses/{response_id}", response_model=AIInterviewResponseOut)
def get_response(response_id: str, db: Session = Depends(get_db)):
    return service.get_response(db, response_id)


@router.post("/responses/{response_id}/score", response_model=AIInterviewResponseOut)
def score_response(response_id: str, db: Session = Depends(get_db)):
    """Trigger ulang scoring manual (auto-scoring saat submit gagal, atau mau dinilai ulang)."""
    return service.score_response(db, response_id)


@router.post("/responses/{response_id}/review", response_model=AIInterviewResponseOut)
def review_response(
    response_id: str,
    payload: AIInterviewReviewIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Gate wajib — skor AI tidak dianggap final di UI manapun sebelum endpoint ini dipanggil."""
    return service.review_response(db, user, response_id, payload)


@router.post("/responses/{response_id}/resend-invite", response_model=AIInterviewResponseOut)
def resend_invite(response_id: str, db: Session = Depends(get_db)):
    return service.resend_invite(db, response_id)


# ---------- Sisi kandidat — publik, tanpa autentikasi ----------

public_router = APIRouter(prefix="/ai-interview/session", tags=["ai-interview-public"])

_SESSION_RATE_MAX = 30
_SESSION_RATE_WINDOW_SEC = 3600


def _check_rate_limit(db: Session) -> None:
    ip, _ = get_request_meta()
    limiter = get_limiter("ai_interview_session")
    key = ip or "unknown"
    allowed, retry_after = limiter.check(
        db, key, max_attempts=_SESSION_RATE_MAX, window_seconds=_SESSION_RATE_WINDOW_SEC
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan dari lokasi ini. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(db, key, window_seconds=_SESSION_RATE_WINDOW_SEC)


@public_router.get("/{token}", response_model=PublicInterviewSessionOut)
def get_session(token: str, db: Session = Depends(get_db)):
    _check_rate_limit(db)
    return service.get_session(db, token)


@public_router.post("/{token}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_session(token: str, db: Session = Depends(get_db)):
    service.start_session(db, token)


@public_router.post("/{token}/answer", status_code=status.HTTP_204_NO_CONTENT)
def submit_answer(token: str, payload: AnswerIn, db: Session = Depends(get_db)):
    service.submit_answer(db, token, payload)


@public_router.post("/{token}/submit", response_model=PublicInterviewSessionOut)
def submit_session(token: str, db: Session = Depends(get_db)):
    service.submit_session(db, token)
    return service.get_session(db, token)


# ---------- AI Interview Fase 2: percakapan suara real-time ----------


@public_router.post("/{token}/voice/start", response_model=VoiceSessionOut)
async def start_voice_session(token: str, db: Session = Depends(get_db)):
    _check_rate_limit(db)
    return await service.start_voice_session(db, token)


@public_router.get("/{token}/voice/context", response_model=VoiceContextOut)
def get_voice_context(token: str, db: Session = Depends(get_db)):
    """Dipanggil agent worker (bukan browser kandidat) — kredensial sama
    (`invite_token`), tapi TIDAK di-rate-limit ketat seperti endpoint
    kandidat karena dipanggil sekali per sesi oleh agent, bukan berulang
    dari browser publik."""
    return service.get_voice_context(db, token)


@public_router.post("/{token}/voice/complete", response_model=PublicInterviewSessionOut)
def complete_voice_session(token: str, payload: VoiceCompleteIn, db: Session = Depends(get_db)):
    service.complete_voice_session(db, token, payload.transcript)
    return service.get_session(db, token)
