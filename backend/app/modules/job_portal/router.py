"""Router publik Job Portal (PRD v3.1 Patch 5) — TANPA autentikasi sama
sekali, mirror pola `payroll/router.py::public_router` (token/slug based,
bukan JWT)."""

import json

from app.core.database import get_db
from app.core.ratelimit import get_limiter
from app.core.tenancy import get_request_meta
from app.modules.job_portal import service
from app.modules.job_portal.schemas import (
    ApplicationStatusOut,
    ApplyIn,
    JobApplicationOut,
    PublicJobOrderDetailOut,
    PublicJobOrderOut,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

router = APIRouter(prefix="/public", tags=["job-portal"])

_APPLY_RATE_MAX = 5
_APPLY_RATE_WINDOW_SEC = 3600


@router.get("/{tenant_slug}/job-orders", response_model=list[PublicJobOrderOut])
def list_job_orders(tenant_slug: str, db: Session = Depends(get_db)):
    return service.list_public_job_orders(db, tenant_slug)


@router.get("/{tenant_slug}/job-orders/{jo_id}", response_model=PublicJobOrderDetailOut)
def get_job_order(tenant_slug: str, jo_id: str, db: Session = Depends(get_db)):
    return service.get_public_job_order(db, tenant_slug, jo_id)


@router.post("/{tenant_slug}/job-orders/{jo_id}/apply", response_model=JobApplicationOut)
async def apply(
    tenant_slug: str,
    jo_id: str,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    consent: bool = Form(False),
    screening_answers: str = Form("{}"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Rate-limit per IP — cegah spam lamaran (pola sama seperti login/reset-password)."""
    ip, _ = get_request_meta()
    limiter = get_limiter("job_portal_apply")
    key = ip or "unknown"
    allowed, retry_after = limiter.check(
        db, key, max_attempts=_APPLY_RATE_MAX, window_seconds=_APPLY_RATE_WINDOW_SEC
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan lamaran dari lokasi ini. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(db, key, window_seconds=_APPLY_RATE_WINDOW_SEC)

    try:
        answers = json.loads(screening_answers) if screening_answers else {}
        if not isinstance(answers, dict):
            answers = {}
    except (TypeError, ValueError):
        answers = {}

    payload = ApplyIn(
        full_name=full_name,
        email=email,
        phone=phone,
        consent=consent,
        screening_answers=answers,
    )
    return await service.apply_to_job_order(db, tenant_slug, jo_id, payload, file)


@router.get("/applications/{token}", response_model=ApplicationStatusOut)
def application_status(token: str, db: Session = Depends(get_db)):
    return service.get_application_status(db, token)
