"""Fase 11 — Chat Workspace service: channel, message, reaction, access control.

Aturan akses (PRD §9.2):
- Staff roles: semua channel tenant + DM siapa pun.
- Karyawan outsourcing (role karyawan): hanya channel proyek tempatnya
  terdaftar sebagai member; DM hanya dengan sesama member channel tersebut.
"""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import parse_uuid
from app.modules.chat.models import (
    Channel,
    ChatChannelMember,
    ChatMessage,
    ChatMessageReaction,
)

STAFF_ROLES = {
    "admin",
    "management",
    "finance",
    "hr",
    "business_dev",
    "recruiter",
    "operations",
}


def _is_member(db: Session, channel_id, user_id) -> bool:
    count = db.scalar(
        select(func.count(ChatChannelMember.id)).where(
            ChatChannelMember.channel_id == parse_uuid(str(channel_id)),
            ChatChannelMember.user_id == parse_uuid(str(user_id)),
        )
    )
    return (count or 0) > 0


def is_staff(user) -> bool:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return role != "karyawan"


def _assert_can_read(db: Session, user, channel: Channel) -> None:
    if is_staff(user):
        return
    if not _is_member(db, channel.id, user.id):
        raise HTTPException(status_code=403, detail="Anda bukan anggota channel ini")


def _assert_can_post(db: Session, user, channel: Channel) -> None:
    _assert_can_read(db, user, channel)
    if channel.channel_type == "broadcast":
        if user.role not in ("admin", "operations", "management"):
            raise HTTPException(
                status_code=403,
                detail="Broadcast channel hanya untuk admin/Ops",
            )


# ---------- Channels ----------


def create_channel(
    db: Session,
    *,
    user,
    name: str,
    channel_type: str = "public",
    member_ids: list | None = None,
) -> Channel:
    slug = name.lower().replace(" ", "-").replace("#", "")[:120]
    ch = Channel(
        name=name, slug=slug, channel_type=channel_type, created_by_id=parse_uuid(str(user.id))
    )
    db.add(ch)
    db.flush()
    # Creator selalu member + admin
    db.add(ChatChannelMember(channel_id=ch.id, user_id=parse_uuid(str(user.id)), is_admin=True))
    for uid in member_ids or []:
        if uid != user.id:
            db.add(ChatChannelMember(channel_id=ch.id, user_id=uid))
    # Karyawan non-staff otomatis jadi member private/broadcast channel
    if channel_type in ("private", "broadcast") and member_ids:
        pass  # sudah ditambahkan di atas
    db.commit()
    db.refresh(ch)
    return ch


def list_channels(db: Session, user) -> list[dict]:
    """Channel yang bisa dilihat user."""
    staff = is_staff(user)
    stmt = select(Channel).where(Channel.tenant_id == user.tenant_id)
    if not staff:
        # Karyawan hanya melihat channel yang dia member.
        member_ids = select(ChatChannelMember.channel_id).where(
            ChatChannelMember.user_id == parse_uuid(str(user.id))
        )
        stmt = stmt.where(Channel.id.in_(member_ids))
    channels = list(db.execute(stmt.order_by(Channel.name)).scalars())
    result = []
    for ch in channels:
        member_count = db.scalar(
            select(func.count(ChatChannelMember.id)).where(ChatChannelMember.channel_id == ch.id)
        )
        last_msg = db.execute(
            select(ChatMessage)
            .where(ChatMessage.channel_id == ch.id, ChatMessage.deleted_at.is_(None))
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        unread = 0
        if not staff and user.role == "karyawan":
            read_state = db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.channel_id == ch.id,
                    ChatMessage.created_at
                    > (_last_read_at(db, ch.id, user.id) or datetime(2000, 1, 1)),
                    ChatMessage.sender_id != parse_uuid(str(user.id)),
                    ChatMessage.deleted_at.is_(None),
                )
            ).scalar()
            unread = int(read_state or 0)
        result.append(
            {
                "id": str(ch.id),
                "name": ch.name,
                "slug": ch.slug,
                "channel_type": ch.channel_type,
                "member_count": member_count or 0,
                "last_message_preview": (
                    f"{last_msg.content[:60]}..."
                    if last_msg and len(last_msg.content) > 60
                    else (last_msg.content if last_msg else "")
                ),
                "unread_count": unread,
            }
        )
    return result


def _last_read_at(db: Session, channel_id, user_id):
    from app.modules.chat.models import ChatMessageReaction  # noqa

    latest_seen = db.execute(
        select(func.max(ChatMessage.created_at)).where(
            ChatMessage.channel_id == channel_id,
            ChatMessage.sender_id == parse_uuid(str(user_id)),
            ChatMessage.deleted_at.is_(None),
        )
    ).scalar()
    return latest_seen


def get_channel_with_access_check(db: Session, user, channel_id) -> Channel:
    ch = db.get(Channel, _parse(channel_id))
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel tidak ditemukan")
    _assert_can_read(db, user, ch)
    return ch


def add_member(db: Session, user, channel_id: str, new_user_id) -> dict:
    ch = get_channel_with_access_check(db, user, channel_id)
    if not is_staff(user) and user.role == "karyawan":
        raise HTTPException(status_code=403, detail="Karyawan tidak dapat menambah member")
    if _is_member(db, ch.id, new_user_id):
        raise HTTPException(status_code=409, detail="User sudah menjadi member")
    db.add(ChatChannelMember(channel_id=ch.id, user_id=parse_uuid(str(new_user_id))))
    db.commit()
    return {"channel_id": str(ch.id), "user_id": str(new_user_id), "added": True}


# ---------- Messages ----------


def send_message(
    db: Session, *, user, channel_id: str, content: str, parent_id=None
) -> ChatMessage:
    ch = get_channel_with_access_check(db, user, channel_id)
    _assert_can_post(db, user, ch)
    content = content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Pesan tidak boleh kosong")
    msg = ChatMessage(
        channel_id=ch.id,
        sender_id=parse_uuid(str(user.id)),
        content=content[:5000],
        parent_id=_parse(parent_id) if parent_id else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_messages(
    db: Session, user, channel_id: str, parent_id: str | None = None, limit: int = 50
) -> list[ChatMessage]:
    ch = get_channel_with_access_check(db, user, channel_id)
    stmt = (
        select(ChatMessage)
        .options(joinedload(ChatMessage.reactions))
        .where(ChatMessage.channel_id == ch.id, ChatMessage.deleted_at.is_(None))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    if parent_id:
        stmt = stmt.where(ChatMessage.parent_id == _parse(parent_id))
    else:
        stmt = stmt.where(ChatMessage.parent_id.is_(None))
    return list(reversed(db.execute(stmt).unique().scalars().all()))


def edit_message(db: Session, user, message_id: str, content: str) -> ChatMessage:
    msg = db.get(ChatMessage, _parse(message_id))
    if msg is None:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan")
    if msg.sender_id != parse_uuid(str(user.id)):
        raise HTTPException(status_code=403, detail="Hanya pengirim yang bisa mengedit")
    msg.content = content.strip()[:5000]
    msg.edited_at = datetime.now(UTC)
    db.commit()
    db.refresh(msg)
    return msg


def delete_message(db: Session, user, message_id: str) -> None:
    msg = db.get(ChatMessage, _parse(message_id))
    if msg is None:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan")
    can_delete = msg.sender_id == user.id or is_staff(user)
    if not can_delete:
        raise HTTPException(status_code=403, detail="Tidak memiliki izin hapus pesan")
    msg.deleted_at = datetime.now(UTC)
    db.commit()


# ---------- Reactions ----------


def toggle_reaction(db: Session, user, message_id: str, emoji: str) -> dict:
    existing = db.execute(
        select(ChatMessageReaction).where(
            ChatMessageReaction.message_id == _parse(message_id),
            ChatMessageReaction.user_id == parse_uuid(str(user.id)),
            ChatMessageReaction.emoji == emoji[:20],
        )
    ).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.commit()
        return {"message_id": message_id, "emoji": emoji, "active": False}
    reaction = ChatMessageReaction(
        message_id=_parse(message_id), user_id=parse_uuid(str(user.id)), emoji=emoji[:20]
    )
    db.add(reaction)
    db.commit()
    return {"message_id": message_id, "emoji": emoji, "active": True}


# ---------- Read state ----------


def mark_all_read(db: Session, user, channel_id: str) -> dict:
    ch = get_channel_with_access_check(db, user, channel_id)
    latest = db.execute(
        select(func.max(ChatMessage.created_at)).where(
            ChatMessage.channel_id == ch.id, ChatMessage.deleted_at.is_(None)
        )
    ).scalar()
    count = db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.channel_id == ch.id,
            ChatMessage.sender_id != parse_uuid(str(user.id)),
            ChatMessage.deleted_at.is_(None),
            ChatMessage.created_at > (_last_read_at(db, ch.id, user.id) or datetime(2000, 1, 1)),
        )
    ).scalar()
    # Update sender's own messages to simulate read state tracking
    # (v1 sederhana: set timestamp terakhir dilihat via max created_at milik user)
    return {"channel_id": str(ch.id), "marked": int(count or 0), "latest": str(latest)}


def _parse(value):
    import uuid as _uuid

    try:
        return _uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _serialize_message(msg: ChatMessage, current_user_id) -> dict:
    reactions: dict[str, list[str]] = {}
    for r in msg.reactions:
        reactions.setdefault(r.emoji, []).append(str(r.user_id))
    base: dict = {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "content": msg.content if msg.deleted_at is None else "(pesan dihapus)",
        "parent_id": str(msg.parent_id) if msg.parent_id else None,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "created_at": msg.created_at.isoformat(),
        "reactions": {e: len(u) for e, u in reactions.items()},
        "is_own": parse_uuid(str(msg.sender_id)) == parse_uuid(str(current_user_id)),
    }
    if hasattr(msg, "message_type"):
        base["message_type"] = getattr(msg, "message_type", "text")
        base["card_data"] = getattr(msg, "card_data", None)
        base["actions"] = getattr(msg, "actions", None)
    return base


# ---------- Card interaktif (PR & payroll) ----------


def send_card_message(
    db: Session,
    *,
    user,
    channel_id: str,
    title: str,
    body: str | None,
    actions: list[dict],
    card_type: str = "pr_approval",
) -> ChatMessage:
    """Kirim pesan kartu dengan tombol aksi; notifikasi in-app juga dibuat."""
    ch = get_channel_with_access_check(db, user, channel_id)
    msg = ChatMessage(
        channel_id=ch.id,
        sender_id=parse_uuid(str(user.id)),
        content=title,
        message_type="card",
        card_data={"title": title, "body": body or "", "type": card_type},
        actions=actions,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # Best-effort WS broadcast (polling fallback covers v1)
    try:
        import asyncio

        from app.modules.chat.ws_manager import manager as _ws

        coro = _ws.broadcast(
            channel_id=str(ch.id),
            payload={"event": "new_message", "message": _serialize_message(msg, user.id)},
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(coro)
        except RuntimeError:
            pass
    except Exception:
        pass
    return msg


def handle_card_action(
    db: Session, *, user, message_id: str, action_id: str, note: str | None = None
) -> dict:
    """Dispatch aksi tombol kartu; divalidasi RBAC per aksi."""
    msg = db.get(ChatMessage, _parse(message_id))
    if msg is None:
        raise HTTPException(status_code=404, detail="Pesan kartu tidak ditemukan")
    if not msg.actions:
        raise HTTPException(status_code=422, detail="Pesan ini tidak memiliki aksi")

    for act in msg.actions:
        if act.get("id") == action_id:
            break
    else:
        raise HTTPException(status_code=404, detail="Aksi tidak ditemukan")

    if action_id.startswith("approve_pr:"):
        pr_id = action_id.split(":", 1)[1]
        from app.modules.finance import service as fin_service

        pr = fin_service.decide_payment_request(
            db, user=user, pr_id=pr_id, approved=True, note=note
        )  # noqa: E501
        _post_action_result(
            db,
            user=user,
            original_msg=msg,
            result=f"PR {pr.pr_number} disetujui oleh {getattr(user, 'full_name', '') or user.email}",  # noqa: E501
        )
        return {"status": "approved", "pr_number": pr.pr_number}
    if action_id.startswith("reject_pr:"):
        pr_id = action_id.split(":", 1)[1]
        from app.modules.finance import service as fin_service

        pr = fin_service.decide_payment_request(
            db, user=user, pr_id=pr_id, approved=False, note=note
        )  # noqa: E501
        _post_action_result(
            db,
            user=user,
            original_msg=msg,
            result=f"PR {pr.pr_number} ditolak oleh {getattr(user, 'full_name', '') or user.email}",
        )
        return {"status": "rejected", "pr_number": pr.pr_number}
    if action_id.startswith("execute_pr:"):
        pr_id = action_id.split(":", 1)[1]
        from app.modules.finance import service as fin_service

        pr = fin_service.execute_payment_request(db, user=user, pr_id=pr_id)
        _post_action_result(
            db,
            user=user,
            original_msg=msg,
            result=f"PR {pr.pr_number} dieksekusi Finance",
        )
        return {"status": "executed", "pr_number": pr.pr_number}
    raise HTTPException(status_code=422, detail="Aksi tidak dikenal")


def _post_action_result(db: Session, *, user, original_msg: ChatMessage, result: str) -> None:
    reply = ChatMessage(
        channel_id=original_msg.channel_id,
        sender_id=parse_uuid(str(user.id)),
        content=result,
        parent_id=original_msg.id,
        message_type="system",
    )
    db.add(reply)
    db.commit()


# ---------- Channel otomatis per entitas ----------


def _get_ops_user_ids(db: Session, tenant_id) -> list:
    from app.modules.auth.models import User

    return list(
        db.execute(
            select(User.id).where(
                User.tenant_id == parse_uuid(str(tenant_id)),
                User.role == "operations",
                User.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )


def ensure_job_order_channel(db: Session, job_order) -> Channel | None:
    """#jo-{klien}-{posisi} untuk diskusi job order."""
    try:
        from app.modules.clients.models import Client

        client = db.get(Client, job_order.client_id)
        if client is None:
            return None
        slug = f"jo-{client.name.lower().replace(' ', '-')[:40]}-{job_order.title.lower().replace(' ', '-')[:20]}"  # noqa: E501
        existing = db.execute(
            select(Channel).where(Channel.slug == slug, Channel.tenant_id == job_order.tenant_id)
        ).scalar_one_or_none()
        if existing:
            return existing
        ch = Channel(
            tenant_id=job_order.tenant_id,
            name=f"JO: {job_order.title}",
            slug=slug,
            channel_type="private",
            created_by_id=job_order.tenant_id,
        )
        db.add(ch)
        db.flush()
        for uid in _get_ops_user_ids(db, job_order.tenant_id):
            db.add(ChatChannelMember(channel_id=ch.id, user_id=uid, tenant_id=job_order.tenant_id))
        db.commit()
        db.refresh(ch)
        return ch
    except Exception:
        db.rollback()
        return None


def ensure_project_channel(db: Session, placement) -> Channel | None:
    """#proyek-{klien} untuk karyawan outsourcing + tim Ops proyeknya."""
    try:
        from app.modules.clients.models import Client
        from app.modules.recruitment.models import JobOrder

        jo = db.get(JobOrder, placement.job_order_id)
        if jo is None:
            return None
        client = db.get(Client, jo.client_id)
        if client is None:
            return None
        slug = f"proyek-{client.name.lower().replace(' ', '-')[:40]}"
        existing = db.execute(
            select(Channel).where(Channel.slug == slug, Channel.tenant_id == placement.tenant_id)
        ).scalar_one_or_none()
        if existing:
            return existing
        ch = Channel(
            tenant_id=placement.tenant_id,
            name=f"Proyek: {client.name}",
            slug=slug,
            channel_type="private",
            created_by_id=placement.tenant_id,
        )
        db.add(ch)
        db.flush()
        for uid in _get_ops_user_ids(db, placement.tenant_id):
            db.add(ChatChannelMember(channel_id=ch.id, user_id=uid, tenant_id=placement.tenant_id))
        db.commit()
        db.refresh(ch)
        return ch
    except Exception:
        db.rollback()
        return None


def ensure_payroll_channel(db: Session, run) -> Channel | None:
    """#payroll-{bulan} ringkasan per klien sebagai pesan sistem."""
    try:
        slug = f"payroll-{run.year}-{str(run.month).zfill(2)}"
        existing = db.execute(
            select(Channel).where(Channel.slug == slug, Channel.tenant_id == run.tenant_id)
        ).scalar_one_or_none()
        if existing:
            return existing
        ch = Channel(
            tenant_id=run.tenant_id,
            name=f"Payroll {run.month}/{run.year}",
            slug=slug,
            channel_type="private",
            created_by_id=run.tenant_id,
        )
        db.add(ch)
        db.flush()
        for uid in _get_ops_user_ids(db, run.tenant_id):
            db.add(ChatChannelMember(channel_id=ch.id, user_id=uid, tenant_id=run.tenant_id))
        db.commit()
        db.refresh(ch)
        return ch
    except Exception:
        db.rollback()
        return None


def post_payroll_status_message(db: Session, run, text: str) -> None:
    """Posting pesan sistem status payrol ke channel periode (best-effort)."""
    ch = ensure_payroll_channel(db, run)
    if ch is None:
        return
    msg = ChatMessage(
        channel_id=ch.id,
        sender_id=ch.created_by_id,
        content=text,
        message_type="system",
        tenant_id=ch.tenant_id,
    )
    db.add(msg)
    db.commit()
