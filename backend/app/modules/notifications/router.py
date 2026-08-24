from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_tenant_user
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationOut, UnreadCountOut

# Notifikasi in-app milik akun yang sedang login (pola sama dengan /me/*).
router = APIRouter(
    prefix="/me/notifications",
    tags=["selfservice"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_own(db, current_user, unread_only=unread_only)


@router.get("/unread-count", response_model=UnreadCountOut)
def count_unread(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UnreadCountOut(count=service.unread_count(db, current_user))


@router.post("/read-all")
def read_all(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"marked": service.mark_all_read(db, current_user)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.mark_read(db, current_user, notification_id)
