from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.modules.chat import service


def _serialize_message(db, msg, user_id):
    return service._serialize_message(msg, user_id)


# ---------- Authenticated chat API ----------

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[
        Depends(get_current_user),
    ],
)


@router.get("/channels")
def list_channels(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.list_channels(db, user)


@router.post("/channels", status_code=201)
def create_channel(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Nama channel wajib diisi")
    ch_type = str(payload.get("channel_type") or "public")
    if ch_type not in ("public", "private", "dm", "broadcast"):
        raise HTTPException(status_code=422, detail="Tipe channel tidak valid")
    member_ids = payload.get("member_ids") or []
    if not isinstance(member_ids, list):
        member_ids = []
    # Validasi UUID
    try:
        member_ids = [UUID(m) for m in member_ids]
    except ValueError:
        raise HTTPException(status_code=422, detail="member_ids tidak valid")  # noqa: B904
    ch = service.create_channel(
        db, user=user, name=name, channel_type=ch_type, member_ids=member_ids
    )
    return {"id": str(ch.id), "name": ch.name, "channel_type": ch.channel_type}


@router.post("/channels/{channel_id}/members")
def add_member(
    channel_id: str, payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    new_user_id = (payload or {}).get("user_id")
    if not new_user_id:
        raise HTTPException(status_code=422, detail="user_id wajib diisi")
    return service.add_member(db, user, channel_id, new_user_id)


@router.get("/channels/{channel_id}/messages")
def list_messages(
    channel_id: str,
    parent_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    messages = service.list_messages(
        db, user=user, channel_id=channel_id, parent_id=parent_id, limit=limit
    )
    return [service._serialize_message(m, user.id) for m in messages]


@router.post("/channels/{channel_id}/messages", status_code=201)
def send_message(
    channel_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    content = str((payload or {}).get("content") or "")
    parent_id = (payload or {}).get("parent_id")
    msg = service.send_message(
        db, user=user, channel_id=channel_id, content=content, parent_id=parent_id
    )
    return service._serialize_message(msg, user.id)


@router.patch("/messages/{message_id}")
def edit_message(
    message_id: str, payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    content = str((payload or {}).get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="Konten tidak boleh kosong")
    msg = service.edit_message(db, user, message_id, content)
    return service._serialize_message(msg, user.id)


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.delete_message(db, user, message_id)


@router.post("/messages/{message_id}/react")
def toggle_reaction(
    message_id: str, payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    emoji = str((payload or {}).get("emoji") or "")
    if not emoji:
        raise HTTPException(status_code=422, detail="Emoji wajib diisi")
    return service.toggle_reaction(db, user, message_id, emoji)


@router.post("/channels/{channel_id}/read-all")
def mark_read(channel_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.mark_all_read(db, user, channel_id)
