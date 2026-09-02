"""Router Black Lists (riset arsitektur MyOHRIS §2). Staf saja, RBAC
`RECRUITMENT_ROLES` -- sama seperti AI Interview, tidak ada role approver
terpisah di AEOS jadi permintaan & review dipagari role yang sama (siapa pun
recruiter/management boleh mengajukan ATAU review, gate-nya ada di alur
request->approve itu sendiri, bukan di pemisahan role)."""

from __future__ import annotations

from uuid import UUID

from app.core.database import get_db
from app.core.permissions import RECRUITMENT_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.blacklist import service
from app.modules.blacklist.models import BlacklistStatus
from app.modules.blacklist.schemas import BlacklistEntryOut, BlacklistRequestIn, BlacklistReviewIn
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/blacklist",
    tags=["blacklist"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*RECRUITMENT_ROLES))],
)


@router.post("/entries", response_model=BlacklistEntryOut)
def request_blacklist(
    payload: BlacklistRequestIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.request_blacklist(db, user, payload.candidate_id, payload.reason)


@router.get("/entries", response_model=list[BlacklistEntryOut])
def list_entries(status: BlacklistStatus | None = Query(None), db: Session = Depends(get_db)):
    return service.list_entries(db, status)


@router.post("/entries/{entry_id}/review", response_model=BlacklistEntryOut)
def review_entry(
    entry_id: UUID,
    payload: BlacklistReviewIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.review_entry(db, user, entry_id, payload.decision, payload.notes)
