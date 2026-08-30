from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, get_current_user
from app.modules.chat import service

# Sengaja tanpa require_roles(...): Chat Workspace itu fitur Foundation
# gratis (PRD v3.0 §2.1) utk seluruh staf tenant yang login, tanpa
# pembatasan role — bukan celah RBAC yang kelewatan. Lihat audit permukaan
# RBAC di core/permissions.py.
router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(get_current_user)])

# Router publik untuk WebSocket (handshake via token query, bukan Bearer header)
ws_router = APIRouter(prefix="/chat", tags=["chat"])


@ws_router.websocket("/ws")
async def chat_ws(websocket: WebSocket, token: str = Query("")):
    """WebSocket chat real-time (PRD §9.4): handshake JWT via query token."""
    from app.core.database import SessionLocal

    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=1008)
        return
    db = SessionLocal()
    try:
        from app.modules.auth.models import User

        user = db.get(User, _parse(user_id))  # type: ignore[attr-defined]
        if user is None or not user.is_active:
            await websocket.close(code=1008)
            return
        tenant_id = str(user.tenant_id or "platform")
        user_id_str = str(user.id)

        from app.modules.chat.ws_manager import manager

        await manager.connect(tenant_id, user_id_str, websocket)
        try:
            while True:
                await websocket.receive_text()  # heartbeat / typing — abaikan v1
        except Exception:
            pass
        finally:
            await manager.disconnect(tenant_id, user_id_str)
    finally:
        db.close()


def _parse(value):
    import uuid as _uuid

    try:
        return _uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


@router.get("/channels")
def list_channels(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.list_channels(db, user)


@router.get("/search")
def search_messages(
    q: str = Query(..., min_length=2),
    channel_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Pencarian pesan (ILIKE) ter-scope channel yang boleh dibaca."""
    return service.search_messages(db, user, q=q, channel_id=channel_id)


@router.get("/users/search")
def search_users(
    q: str = Query("", min_length=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Autocomplete mention @user — ter-scope proyek untuk karyawan."""
    return service.search_users_for_mention(db, user, q=q)


@router.post("/channels", status_code=201)
def create_channel(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Nama channel wajib diisi")
    ch_type = str(payload.get("channel_type") or "public")
    if ch_type not in ("public", "private", "dm", "broadcast"):
        raise HTTPException(status_code=422, detail="Tipe channel tidak valid")
    member_ids = payload.get("member_ids") or []
    ch = service.create_channel(
        db,
        user=user,
        name=name,
        channel_type=ch_type,
        member_ids=member_ids if isinstance(member_ids, list) else [],
    )
    return {"id": str(ch.id), "name": ch.name, "channel_type": ch.channel_type}


@router.post("/channels/{channel_id}/members")
def add_member(
    channel_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
    message_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
    message_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    emoji = str((payload or {}).get("emoji") or "")
    if not emoji:
        raise HTTPException(status_code=422, detail="Emoji wajib diisi")
    return service.toggle_reaction(db, user, message_id, emoji)


@router.post("/channels/{channel_id}/read-all")
def mark_read(channel_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.mark_all_read(db, user, channel_id)


@router.post("/messages/{message_id}/actions/{action_id}")
def handle_card_action(
    message_id: str,
    action_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Eksekusi aksi kartu interaktif (PR/payroll) dari chat."""
    note = (payload or {}).get("note")
    return service.handle_card_action(
        db, user=user, message_id=message_id, action_id=action_id, note=note
    )


# ---------- Fase 12: AI Kolaborasi ----------

ai_router = APIRouter(prefix="/chat", tags=["chat-ai"])


@ai_router.post("/messages/{message_id}/summarize")
def summarize_thread(
    message_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Rangkum thread menjadi poin keputusan/tugas; balasan diposting AEOS."""
    return service.summarize_thread(db, user=user, root_message_id=message_id)


@ai_router.get("/digest")
def daily_digest(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Digest harian deterministik: approval menunggu, SLA, kontrak, invoice."""
    from app.modules.ai import collab

    return collab.daily_digest(db, user)


@ai_router.post("/ask")
def ask_aeos(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Tanya @AEOS langsung tanpa channel (UI ringan)."""
    from app.modules.ai import collab

    question = str((payload or {}).get("question") or "").strip()
    return collab.answer_question(db, user, question)
