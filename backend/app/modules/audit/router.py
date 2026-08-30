from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import AUDIT_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.audit import service
from app.modules.audit.schemas import AuditListOut

# Jejak audit sensitif: hanya management (admin melewati semua guard).
router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*AUDIT_ROLES))],
)


@router.get("/logs", response_model=AuditListOut)
def list_logs(
    action_prefix: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    user_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.query_logs(
        db,
        action_prefix=action_prefix,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return AuditListOut(total=total, items=[service.to_out(r) for r in rows])
