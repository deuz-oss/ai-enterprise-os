"""Fase 11 — Chat Workspace service: channel, message, reaction, access control.

Aturan akses (PRD §9.2):
- Staff roles: semua channel tenant + DM siapa pun.
- Karyawan outsourcing (role karyawan): hanya channel proyek tempatnya
  terdaftar sebagai member; DM hanya dengan sesama member channel tersebut.
"""

import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, func, select, text, tuple_
from sqlalchemy.orm import Session, joinedload

from app.core.database import parse_uuid
from app.modules.chat.models import (
    Channel,
    ChatChannelMember,
    ChatFile,
    ChatMessage,
    ChatMessageReaction,
)

logger = logging.getLogger(__name__)

STAFF_ROLES = {
    "admin",
    "management",
    "finance",
    "hr",
    "business_dev",
    "recruiter",
    "operations",
}

_MENTION_RE = re.compile(r"@([^\s@]+(?:\s+[^\s@]+)?)")
_MENTION_TRAILING_PUNCT_RE = re.compile(r"[.,!?;:]+$")


def _extract_mention_tokens(content: str) -> list[str]:
    """Ambil token @mention dari teks, buang tanda baca penutup yang lazim
    menyusul nama orang dalam kalimat (mis. "@Budi Santoso, tolong...").
    Tanpa ini token mentah ikut membawa koma sehingga gagal cocok dengan
    nama asli user -- regresi nyata: "@Nama Dua Kata, ..." tidak pernah
    match walau usernya persis ada, ketahuan lewat tes notifikasi mention."""
    raw_mentions = _MENTION_RE.findall(content)
    return [_MENTION_TRAILING_PUNCT_RE.sub("", m.strip()) for m in raw_mentions]


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


def _channel_audience_ids(db: Session, channel: Channel) -> set[str]:
    """Siapa yang boleh melihat channel ini: semua staff tenant + member eksplisit.

    Meniru aturan `_assert_can_read` (staff bebas akses channel apa pun,
    karyawan hanya jika jadi member) supaya event WS tidak bocor ke user
    yang REST endpoint-nya sendiri tidak akan izinkan membaca channel ini.
    """
    from app.modules.auth.models import User

    staff_ids = set(
        str(uid)
        for uid in db.execute(
            select(User.id).where(
                User.tenant_id == channel.tenant_id,
                User.role.in_(STAFF_ROLES),
                User.is_active.is_(True),
            )
        ).scalars()
    )
    member_ids = set(
        str(uid)
        for uid in db.execute(
            select(ChatChannelMember.user_id).where(ChatChannelMember.channel_id == channel.id)
        ).scalars()
    )
    return staff_ids | member_ids


def _notify_channel(db: Session, channel: Channel, event: str) -> None:
    """Signal WS best-effort (tanpa konten pesan) agar client refetch.

    Konten pesan sengaja TIDAK dikirim di payload — client cuma dipicu untuk
    refetch REST (yang sudah ter-scope akses dengan benar), jadi payload WS
    aman dilihat siapa pun yang menerimanya secara tidak sengaja.
    """
    try:
        import asyncio

        from app.modules.chat.ws_manager import manager as _ws

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # tanpa event loop aktif (mis. konteks test sync) — lewati notifikasi WS
        audience = _channel_audience_ids(db, channel)
        payload = {"event": event, "channel_id": str(channel.id)}
        loop.create_task(
            _ws.broadcast(tenant_id=str(channel.tenant_id), payload=payload, user_ids=audience)
        )
    except Exception:
        pass


# ---------- Unread counter model (ala Mattermost) ----------
#
# unread_count = channel.total_msg_count - member.msg_count (clamp >= 0).
# Menghindari scan tabel chat_messages tiap render sidebar; baca & tulis O(1).


def _default_notify_level(channel_type: str) -> str:
    """DM secara wajar dianggap penting -- default 'all' (tiap pesan jadi
    badge). Channel/broadcast default 'mentions' (cuma @mention yang jadi
    badge merah + notifikasi bel), sama seperti default Mattermost."""
    return "all" if channel_type == "dm" else "mentions"


def _get_or_create_member(db: Session, channel: Channel, user_id) -> ChatChannelMember:
    uid = parse_uuid(str(user_id))
    member = db.execute(
        select(ChatChannelMember).where(
            ChatChannelMember.channel_id == channel.id, ChatChannelMember.user_id == uid
        )
    ).scalar_one_or_none()
    if member is None:
        member = ChatChannelMember(
            channel_id=channel.id,
            user_id=uid,
            tenant_id=channel.tenant_id,
            notify_level=_default_notify_level(channel.channel_type),
        )
        db.add(member)
        db.flush()
    return member


def _mark_caught_up(db: Session, channel: Channel, user_id) -> None:
    """Tandai user sudah melihat channel sampai pesan terbaru saat ini."""
    member = _get_or_create_member(db, channel, user_id)
    member.msg_count = channel.total_msg_count
    member.mention_count = 0
    member.last_viewed_at = datetime.now(UTC)
    db.commit()


def _mark_mentioned(
    db: Session, channel: Channel, user_id, *, sender=None, content: str = ""
) -> None:
    member = _get_or_create_member(db, channel, user_id)
    if member.notify_level == "none":
        return  # channel dibisukan user ini -- tidak dihitung, tidak diberi tahu
    member.mention_count += 1
    db.commit()
    if sender is not None:
        _create_mention_notification(
            db, channel=channel, member_user_id=user_id, sender=sender, content=content
        )


def _apply_all_level_mentions(
    db: Session, channel: Channel, *, mention_ids: set[str], sender_id
) -> None:
    """Anggota dengan `notify_level == "all"` menganggap SETIAP pesan
    sebagai mention untuk keperluan badge -- TAPI sengaja tidak memicu
    notifikasi bel/email (beda dari @mention asli di `_mark_mentioned`),
    supaya channel yang ramai tidak membanjiri bel/email tiap pesan."""
    sender_uuid = parse_uuid(str(sender_id))
    members = db.execute(
        select(ChatChannelMember).where(
            ChatChannelMember.channel_id == channel.id,
            ChatChannelMember.notify_level == "all",
        )
    ).scalars()
    changed = False
    for m in members:
        if m.user_id == sender_uuid or str(m.user_id) in mention_ids:
            continue
        m.mention_count += 1
        changed = True
    if changed:
        db.commit()


def _create_mention_notification(
    db: Session, *, channel: Channel, member_user_id, sender, content: str
) -> None:
    """Teruskan @mention ke bel notifikasi in-app (+ email bila SMTP aktif)
    -- integrasi nyata dengan `app.modules.notifications`, bukan cuma
    badge di halaman Chat. Gagal mengirim tidak boleh menggagalkan pesan."""
    try:
        from app.modules.notifications import service as notif_service

        sender_name = getattr(sender, "full_name", None) or getattr(sender, "email", "Seseorang")
        notif_service.notify(
            db,
            user_id=member_user_id,
            title=f"{sender_name} menyebut Anda di #{channel.name}",
            body=content[:200] if content else None,
            category="chat_mention",
            entity_type="chat_channel",
            entity_id=channel.id,
        )
    except Exception:  # noqa: BLE001 - notifikasi tidak boleh mematahkan pesan
        logger.exception("Gagal membuat notifikasi mention chat")


VALID_NOTIFY_LEVELS = {"all", "mentions", "none"}


def set_notify_level(db: Session, user, channel_id: str, level: str) -> dict:
    if level not in VALID_NOTIFY_LEVELS:
        raise HTTPException(status_code=422, detail="Level notifikasi tidak valid")
    ch = get_channel_with_access_check(db, user, channel_id)
    member = _get_or_create_member(db, ch, user.id)
    member.notify_level = level
    db.commit()
    return {"channel_id": str(ch.id), "notify_level": level}


def _resolve_mention_target_ids(
    db: Session, channel: Channel, content: str, exclude_user_id
) -> set[str]:
    """Cari user yang di-@mention di `content`, ter-scope audience channel.

    `@channel`/`@here`/`@all` menandai seluruh audience sebagai di-mention.
    Pengirim sendiri selalu dikecualikan.
    """
    if "@" not in content:
        return set()
    from app.modules.auth.models import User

    raw_mentions = _extract_mention_tokens(content)
    if not raw_mentions:
        return set()

    audience_ids = _channel_audience_ids(db, channel)
    if not audience_ids:
        return set()
    audience_uuids = [uid for aid in audience_ids if (uid := parse_uuid(aid)) is not None]
    users = list(db.execute(select(User).where(User.id.in_(audience_uuids))).scalars())

    targets: set[str] = set()
    broadcast_all = False
    for raw in raw_mentions:
        name = raw.strip().lower()
        if name in ("channel", "here", "all"):
            broadcast_all = True
            continue
        for u in users:
            if name in (u.full_name or "").lower() or name in (u.email or "").lower():
                targets.add(str(u.id))
    if broadcast_all:
        targets.update(audience_ids)
    targets.discard(str(exclude_user_id))
    return targets


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
    default_notify = _default_notify_level(channel_type)
    # Creator selalu member + admin
    db.add(
        ChatChannelMember(
            channel_id=ch.id,
            user_id=parse_uuid(str(user.id)),
            is_admin=True,
            notify_level=default_notify,
        )
    )
    creator_id = parse_uuid(str(user.id))
    seen_ids = {creator_id}
    for raw_uid in member_ids or []:
        uid = parse_uuid(str(raw_uid))
        if uid is None or uid in seen_ids:
            continue
        seen_ids.add(uid)
        db.add(ChatChannelMember(channel_id=ch.id, user_id=uid, notify_level=default_notify))
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
    own_members = {
        m.channel_id: m
        for m in db.execute(
            select(ChatChannelMember).where(
                ChatChannelMember.user_id == parse_uuid(str(user.id)),
                ChatChannelMember.channel_id.in_([c.id for c in channels]),
            )
        ).scalars()
    }
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
        # Model counter ala Mattermost: unread = total_msg_count - msg_count
        # (seen). User tanpa row member (staff yang belum pernah "melihat"
        # channel ini) dianggap belum baca apa pun.
        own_member = own_members.get(ch.id)
        seen = own_member.msg_count if own_member else 0
        mentions = own_member.mention_count if own_member else 0
        unread = max(0, ch.total_msg_count - seen)
        notify_level = (
            own_member.notify_level if own_member else _default_notify_level(ch.channel_type)
        )
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
                "mention_count": mentions,
                "notify_level": notify_level,
            }
        )
    return result


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
    db.add(
        ChatChannelMember(
            channel_id=ch.id,
            user_id=parse_uuid(str(new_user_id)),
            notify_level=_default_notify_level(ch.channel_type),
        )
    )
    db.commit()
    return {"channel_id": str(ch.id), "user_id": str(new_user_id), "added": True}


# ---------- File attachment ----------
#
# Alur: upload dulu berdiri sendiri (`upload_chat_file`, message_id NULL),
# baru "ditempel" ke pesan lewat `file_ids` saat `send_message` dipanggil
# (`_claim_pending_files`) -- meniru alur Mattermost (`POST /files` lalu
# `POST /posts` dengan `file_ids`), bukan multipart+JSON sekaligus, supaya
# UI bisa tampilkan progres unggah sebelum tombol kirim ditekan.

MAX_CHAT_FILE_SIZE = 10 * 1024 * 1024  # 10 MB, sama seperti lampiran cuti ESS


async def upload_chat_file(db: Session, *, user, channel_id: str, file) -> ChatFile:
    from app.core import storage

    ch = get_channel_with_access_check(db, user, channel_id)
    _assert_can_post(db, user, ch)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > MAX_CHAT_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 10 MB")
    file_name = (file.filename or "lampiran")[:255]
    content_type = (file.content_type or "application/octet-stream")[:120]
    object_key = storage.new_object_key(f"chat/{ch.id}", file_name)
    storage.put_object(object_key, data, content_type)
    chat_file = ChatFile(
        channel_id=ch.id,
        uploader_id=parse_uuid(str(user.id)),
        object_key=object_key,
        file_name=file_name,
        mime_type=content_type,
        file_size=len(data),
    )
    db.add(chat_file)
    db.commit()
    db.refresh(chat_file)
    return chat_file


def _claim_pending_files(
    db: Session, *, user, channel: Channel, file_ids: list[str]
) -> list[ChatFile]:
    """Validasi & "tempel" file yang sudah diupload ke pesan yang akan dibuat.

    Ditolak kalau: id tidak valid/tidak ditemukan, channel-nya beda (cegah
    lampiran dari channel lain yang aksesnya berbeda dipakai lintas
    channel), pengunggahnya beda user (cegah pakai lampiran orang lain),
    atau sudah terpasang di pesan lain (cegah dipakai berkali-kali).
    """
    if not file_ids:
        return []
    parsed_ids = [uid for fid in file_ids if (uid := _parse(fid)) is not None]
    if len(parsed_ids) != len(file_ids):
        raise HTTPException(status_code=422, detail="file_id tidak valid")
    files = list(db.execute(select(ChatFile).where(ChatFile.id.in_(parsed_ids))).scalars())
    if len(files) != len(parsed_ids):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    sender_id = parse_uuid(str(user.id))
    for f in files:
        if f.channel_id != channel.id:
            raise HTTPException(status_code=422, detail="Lampiran bukan milik channel ini")
        if f.uploader_id != sender_id:
            raise HTTPException(status_code=403, detail="Lampiran bukan milik Anda")
        if f.message_id is not None:
            raise HTTPException(status_code=409, detail="Lampiran sudah terpasang di pesan lain")
    return files


def _serialize_file(f: ChatFile) -> dict:
    from app.core import storage

    return {
        "id": str(f.id),
        "file_name": f.file_name,
        "mime_type": f.mime_type,
        "file_size": f.file_size,
        "url": storage.presigned_get_url(f.object_key),
    }


# ---------- Messages ----------


def send_message(
    db: Session,
    *,
    user,
    channel_id: str,
    content: str,
    parent_id=None,
    file_ids: list[str] | None = None,
) -> ChatMessage:
    ch = get_channel_with_access_check(db, user, channel_id)
    _assert_can_post(db, user, ch)
    content = content.strip()
    file_ids = file_ids or []
    if not content and not file_ids:
        raise HTTPException(status_code=422, detail="Pesan tidak boleh kosong")
    _validate_mentions(db, user, str(ch.id), content)
    files = _claim_pending_files(db, user=user, channel=ch, file_ids=file_ids)
    msg = ChatMessage(
        channel_id=ch.id,
        sender_id=parse_uuid(str(user.id)),
        content=content[:5000],
        parent_id=_parse(parent_id) if parent_id else None,
    )
    db.add(msg)
    ch.total_msg_count += 1
    mention_ids = _resolve_mention_target_ids(db, ch, content, user.id)
    db.commit()
    db.refresh(msg)
    for f in files:
        f.message_id = msg.id
    db.commit()
    for mentioned_id in mention_ids:
        _mark_mentioned(db, ch, mentioned_id, sender=user, content=content)
    _apply_all_level_mentions(db, ch, mention_ids=mention_ids, sender_id=user.id)
    _mark_caught_up(db, ch, user.id)
    _notify_channel(db, ch, "message.created")

    # Fase 12: slash command dieksekusi server-side; @AEOS memicu asisten AI.
    if content.startswith("/"):
        _handle_slash_command(db, user=user, channel=ch, cmd_msg=msg)
    elif "@aeos" in content.lower():
        try:
            from app.modules.ai.collab import ensure_aeos_user

            ensure_aeos_user(db, user.tenant_id)
            handle_aeos_question(db, user=user, channel=ch, trigger_msg=msg)
        except Exception:  # noqa: BLE001 - asisten tidak boleh menggagalkan pesan
            logger.exception("AEOS reply gagal")
    return msg


# ---------- Fase 12: slash command & asisten AEOS ----------


def _post_aeos_reply(
    db: Session, *, tenant_id, channel: Channel, parent_id, content: str, viewer_id=None
) -> ChatMessage:
    """Posting balasan atas nama bot AEOS (identitas per tenant).

    `parent_id` menentukan level tempat balasan muncul — bukan otomatis
    `parent.id` dari pesan pemicu. Regresi: dulu selalu di-nest sebagai
    balasan thread DI BAWAH pesan pemicu, jadi tak pernah muncul di channel
    utama (yang cuma tampilkan pesan top-level) kecuali user tahu harus
    buka thread — @AEOS/slash command jadi seolah tidak menjawab.

    `viewer_id` (opsional): user yang memicu balasan ini langsung ditandai
    caught-up, karena secara UX dia sedang melihat channel saat bot merespons
    — tanpa ini balasan bot akan selalu muncul sebagai 1 unread baru baginya.
    """
    from app.modules.ai.collab import ensure_aeos_user

    aeos = ensure_aeos_user(db, tenant_id)
    msg = ChatMessage(
        channel_id=channel.id,
        sender_id=aeos.id,
        content=content[:5000],
        parent_id=parent_id,
    )
    db.add(msg)
    channel.total_msg_count += 1
    db.commit()
    db.refresh(msg)
    if viewer_id is not None:
        _mark_caught_up(db, channel, viewer_id)
    _notify_channel(db, channel, "message.created")
    return msg


def handle_aeos_question(db: Session, *, user, channel: Channel, trigger_msg: ChatMessage) -> dict:
    """Jawab pesan ber-mention @AEOS via RAG lintas aplikasi; butuh lisensi ai_addon."""
    from app.modules.ai import collab
    from app.modules.ai.collab import _ai_license_active

    if not _ai_license_active(db, user.tenant_id):
        reply = _post_aeos_reply(
            db,
            tenant_id=user.tenant_id,
            channel=channel,
            parent_id=trigger_msg.parent_id,
            content=(
                "Fitur AI add-on belum aktif untuk workspace ini. "
                "Aktifkan trial dari halaman Aplikasi untuk menggunakan @AEOS."
            ),
            viewer_id=user.id,
        )
        return {"answered": False, "reason": "license", "reply_id": str(reply.id)}

    question = trigger_msg.content.replace("@aeos", "", 1).replace("@AEOS", "", 1).strip()
    result = collab.answer_question(db, user, question or "Berapa ringkasan operasional hari ini?")
    text = result["answer"]
    if result.get("route_to"):
        text += f"\n\n→ Saran routing: tim {result['route_to']['team_label']}"
    reply = _post_aeos_reply(
        db,
        tenant_id=user.tenant_id,
        channel=channel,
        parent_id=trigger_msg.parent_id,
        content=text,
        viewer_id=user.id,
    )
    return {"answered": True, "reply_id": str(reply.id), "route_to": result.get("route_to")}


def summarize_thread(db: Session, *, user, root_message_id: str) -> dict:
    """Rangkum thread (§9.6 poin 2) → poin keputusan/tugas; hasil diposting AEOS."""
    from app.modules.ai import collab

    root = db.get(ChatMessage, _parse(root_message_id))
    if root is None or root.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Pesan thread tidak ditemukan")
    channel = get_channel_with_access_check(db, user, root.channel_id)
    msgs, _ = list_messages(db, user, str(root.channel_id), parent_id=str(root.id), limit=100)
    contents = [m.content for m in msgs]
    if len(contents) < 2:
        raise HTTPException(status_code=422, detail="Thread terlalu pendek untuk dirangkum")

    result = collab.summarize_messages(db, user, contents)
    header = "🧵 *Rangkuman thread*"
    if not result["llm"]:
        header += " (mode deterministik — AI belum aktif)"
    reply = _post_aeos_reply(
        db,
        tenant_id=user.tenant_id,
        channel=channel,
        parent_id=root.id,
        content=f"{header}\n{result['summary']}",
        viewer_id=user.id,
    )
    return {
        "summary": result["summary"],
        "message_count": result["message_count"],
        "reply_id": str(reply.id),
    }


_SLASH_HELP = (
    "Perintah tersedia:\n"
    "`/help` — daftar perintah\n"
    "`/pr status` — ringkasan Payment Request\n"
    "`/jo status [kata kunci]` — status job order\n"
    "`/cuti sisa` — sisa cuti tahunan Anda (hanya di DM)\n"
    "`/cuti ajukan <jenis> <tgl-mulai> <tgl-selesai> [alasan]` — ajukan cuti/izin (hanya di DM)\n"
    "Contoh: `/cuti ajukan izin 2026-09-01 2026-09-02 acara keluarga`\n"
    "Jenis: cuti_tahunan · izin · sakit · cuti_tak_berbayar. Sebut `@AEOS` untuk bertanya."
)


def _handle_slash_command(db: Session, *, user, channel: Channel, cmd_msg: ChatMessage) -> None:
    parts = cmd_msg.content[1:].split()
    name = parts[0].lower() if parts else ""
    args = parts[1:]
    is_worker = getattr(user.role, "value", user.role) == "karyawan"

    def respond(text: str):
        _post_aeos_reply(
            db,
            tenant_id=user.tenant_id,
            channel=channel,
            parent_id=cmd_msg.parent_id,
            content=text,
            viewer_id=user.id,
        )

    try:
        if name == "help":
            respond(_SLASH_HELP)
            return

        # Perintah personal hanya di DM agar data pribadi tak bocor ke channel.
        if name == "cuti":
            if channel.channel_type != "dm":
                respond(
                    "Perintah /cuti bersifat pribadi — silakan lanjut di DM "
                    "(mis. DM dengan @AEOS atau atasan Anda)."
                )
                return
            from datetime import date as date_cls

            from app.modules.ess.schemas import LeaveCreate
            from app.modules.ess.service import create_leave_request, get_own_leave_balance

            if not args or args[0] == "sisa":
                from datetime import date as _date

                bal = get_own_leave_balance(db, user, _date.today().year)
                respond(
                    f"Sisa cuti tahunan Anda: {bal.total_days - bal.used_days} "
                    f"dari {bal.total_days} hari."
                    if bal
                    else "Jatah cuti tahunan belum diatur HR — pengajuan tetap bisa diajukan."
                )
                return
            if args[0] == "ajukan":
                if len(args) < 4:
                    respond(_SLASH_HELP)
                    return
                from datetime import date as date_cls

                leave_type = args[1].lower()
                mapping = {
                    "cuti_tahunan": "cuti_tahunan",
                    "izin": "izin",
                    "sakit": "sakit",
                    "cuti_tak_berbayar": "cuti_tak_berbayar",
                }
                if leave_type not in mapping:
                    respond(f"Jenis '{leave_type}' tidak dikenal. Gunakan: {', '.join(mapping)}")
                    return
                created = create_leave_request(
                    db,
                    user,
                    LeaveCreate(
                        leave_type=mapping[leave_type],  # type: ignore[arg-type]
                        start_date=date_cls.fromisoformat(args[2]),
                        end_date=date_cls.fromisoformat(args[3]),
                        reason=" ".join(args[4:])[:500] or None,
                    ),
                )
                respond(
                    f"✅ Pengajuan {mapping[leave_type]} {created.start_date.isoformat()} "
                    f"s/d {created.end_date.isoformat()} terkirim (menunggu approval HR)."
                )
                return
            respond(_SLASH_HELP)
            return

        if is_worker:
            respond("Perintah ini hanya untuk staf.")
            return

        if name == "pr":
            from app.modules.finance.models import PaymentRequest, PaymentRequestStatus

            rows = (
                db.execute(
                    select(PaymentRequest)
                    .where(
                        PaymentRequest.status.in_(
                            [
                                PaymentRequestStatus.waiting_superior,
                                PaymentRequestStatus.approved,
                            ]
                        )
                    )
                    .order_by(PaymentRequest.created_at.desc())
                    .limit(5)
                )
                .scalars()
                .all()
            )
            if not rows:
                respond("Tidak ada PR yang menunggu aksi saat ini. 🎉")
                return
            lines = [
                f"- {p.pr_number} ({p.pr_type}) Rp{float(p.amount):,.0f} — {p.status.value}"
                for p in rows
            ]
            respond("*PR menunggu/disetujui:*\n" + "\n".join(lines))
            return

        if name == "jo":
            from app.modules.recruitment.models import JobOrder, JobOrderStatus

            stmt = select(JobOrder).where(
                JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.screening])
            )
            if args:
                kw = " ".join(args).lower()
                stmt = stmt.where(JobOrder.title.ilike(f"%{kw}%"))
            jo_rows = list(db.execute(stmt.order_by(JobOrder.created_at.desc()).limit(5)).scalars())
            if not jo_rows:
                respond("Tidak ada job order aktif yang cocok.")
                return
            counts = db.execute(
                select(func.count(JobOrder.id)).where(
                    JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.screening])
                )
            ).scalar()
            lines = [
                f"- {j.title} @ {j.client.name if j.client else '-'} — {j.status.value}"
                + (f", due {j.due_date.isoformat()}" if j.due_date else "")
                for j in jo_rows
            ]
            respond(f"*Job order aktif ({counts} total):*\n" + "\n".join(lines))
            return

        respond(_SLASH_HELP)
    except HTTPException as exc:
        respond(f"⚠️ {exc.detail}")
    except Exception:  # noqa: BLE001
        logger.exception("Slash command gagal")
        respond("⚠️ Perintah gagal dieksekusi. Coba lagi atau hubungi admin.")


def list_messages(
    db: Session,
    user,
    channel_id: str,
    parent_id: str | None = None,
    limit: int = 50,
    before_id: str | None = None,
) -> tuple[list[ChatMessage], bool]:
    """Cursor pagination ala Mattermost: `before_id` = id pesan tertua yang
    sudah dimuat client, dibanding via `(created_at, id)` (bukan cuma
    `created_at`) supaya beberapa pesan dengan timestamp identik tidak
    ke-skip/dobel saat scroll ke atas. Return (pesan urut lama->baru, ada
    histori lebih lama lagi atau tidak).
    """
    ch = get_channel_with_access_check(db, user, channel_id)
    limit = max(1, min(limit, 200))
    stmt = (
        select(ChatMessage)
        .options(joinedload(ChatMessage.reactions), joinedload(ChatMessage.files))
        .where(ChatMessage.channel_id == ch.id, ChatMessage.deleted_at.is_(None))
    )
    if parent_id:
        stmt = stmt.where(ChatMessage.parent_id == _parse(parent_id))
    else:
        stmt = stmt.where(ChatMessage.parent_id.is_(None))

    if before_id:
        anchor_id = _parse(before_id)
        if anchor_id is not None:
            # Sengaja bandingkan lewat subquery (bukan `anchor.created_at`
            # dari objek Python yang sudah di-load) -- SQLite menyimpan
            # DateTime sebagai TEXT tanpa affinity ketat; datetime Python
            # yang di-roundtrip lalu dikirim ulang sebagai bind parameter
            # ternyata diserialize BEDA format (dapat suffix `.000000`) dari
            # representasi asli hasil `func.now()` saat INSERT, jadi
            # perbandingan tuple jadi string compare yang salah dan selalu
            # bernilai true (regresi nyata -- ketahuan lewat test cursor
            # pagination: page tidak pernah berubah, `before_id` diabaikan
            # begitu saja). Subquery membandingkan nilai kolom vs kolom
            # langsung di SQL, tanpa lewat roundtrip Python -- aman di
            # SQLite maupun Postgres.
            anchor_created_at = (
                select(ChatMessage.created_at).where(ChatMessage.id == anchor_id).scalar_subquery()
            )
            anchor_id_col = (
                select(ChatMessage.id).where(ChatMessage.id == anchor_id).scalar_subquery()
            )
            stmt = stmt.where(
                tuple_(ChatMessage.created_at, ChatMessage.id)
                < tuple_(anchor_created_at, anchor_id_col)
            )

    # Ambil satu ekstra untuk tahu apakah masih ada histori lebih lama,
    # tanpa query COUNT(*) terpisah.
    stmt = stmt.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).unique().scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    return list(reversed(rows)), has_more


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
    ch = db.get(Channel, msg.channel_id)
    if ch is not None:
        _notify_channel(db, ch, "message.updated")
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
    ch = db.get(Channel, msg.channel_id)
    if ch is not None:
        _notify_channel(db, ch, "message.deleted")


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
        _notify_reaction_channel(db, message_id)
        return {"message_id": message_id, "emoji": emoji, "active": False}
    reaction = ChatMessageReaction(
        message_id=_parse(message_id), user_id=parse_uuid(str(user.id)), emoji=emoji[:20]
    )
    db.add(reaction)
    db.commit()
    _notify_reaction_channel(db, message_id)
    return {"message_id": message_id, "emoji": emoji, "active": True}


def _notify_reaction_channel(db: Session, message_id: str) -> None:
    msg = db.get(ChatMessage, _parse(message_id))
    if msg is None:
        return
    ch = db.get(Channel, msg.channel_id)
    if ch is not None:
        _notify_channel(db, ch, "message.reaction")


# ---------- Pinned posts ----------


def toggle_pin(db: Session, user, message_id: str) -> dict:
    """Syarat sama dengan bisa posting di channel -- bukan cuma admin,
    meniru default Mattermost (anggota channel bebas pin/unpin)."""
    msg = db.get(ChatMessage, _parse(message_id))
    if msg is None or msg.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan")
    ch = db.get(Channel, msg.channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel tidak ditemukan")
    _assert_can_post(db, user, ch)
    msg.is_pinned = not msg.is_pinned
    msg.pinned_at = datetime.now(UTC) if msg.is_pinned else None
    msg.pinned_by_id = parse_uuid(str(user.id)) if msg.is_pinned else None
    db.commit()
    _notify_channel(db, ch, "message.pinned" if msg.is_pinned else "message.unpinned")
    return {"message_id": str(msg.id), "is_pinned": msg.is_pinned}


def list_pinned_messages(db: Session, user, channel_id: str) -> list[dict]:
    ch = get_channel_with_access_check(db, user, channel_id)
    stmt = (
        select(ChatMessage)
        .options(joinedload(ChatMessage.reactions), joinedload(ChatMessage.files))
        .where(
            ChatMessage.channel_id == ch.id,
            ChatMessage.is_pinned.is_(True),
            ChatMessage.deleted_at.is_(None),
        )
        .order_by(ChatMessage.pinned_at.desc())
    )
    msgs = list(db.execute(stmt).unique().scalars())
    return [_serialize_message(m, user.id) for m in msgs]


# ---------- Read state ----------


def mark_all_read(db: Session, user, channel_id: str) -> dict:
    """ "Lihat" channel: snapshot msg_count ke total saat ini, reset mention.

    Sebelumnya endpoint ini cuma MENGHITUNG unread tanpa menyimpan apa pun —
    klik "Tandai dibaca" tidak pernah benar-benar mengubah state, jadi badge
    unread tidak pernah berkurang. Sekarang persisten via `ChatChannelMember`.
    """
    ch = get_channel_with_access_check(db, user, channel_id)
    member = _get_or_create_member(db, ch, user.id)
    marked = max(0, ch.total_msg_count - member.msg_count)
    member.msg_count = ch.total_msg_count
    member.mention_count = 0
    member.last_viewed_at = datetime.now(UTC)
    db.commit()
    return {
        "channel_id": str(ch.id),
        "marked": marked,
        "last_viewed_at": member.last_viewed_at.isoformat(),
    }


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
        "files": [_serialize_file(f) for f in msg.files] if msg.deleted_at is None else [],
        "is_pinned": msg.is_pinned,
        "pinned_at": msg.pinned_at.isoformat() if msg.pinned_at else None,
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
    ch.total_msg_count += 1
    db.commit()
    db.refresh(msg)
    _mark_caught_up(db, ch, user.id)
    _notify_channel(db, ch, "message.created")
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
    ch = db.get(Channel, original_msg.channel_id)
    if ch is not None:
        ch.total_msg_count += 1
    db.add(reply)
    db.commit()
    if ch is not None:
        _mark_caught_up(db, ch, user.id)
        _notify_channel(db, ch, "message.created")


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
        creator_id = _get_admin_user_id(db, job_order.tenant_id) or job_order.tenant_id
        ch = Channel(
            tenant_id=job_order.tenant_id,
            name=f"JO: {job_order.title}",
            slug=slug,
            channel_type="private",
            created_by_id=creator_id,
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


def _get_admin_user_id(db: Session, tenant_id) -> UUID | None:
    from app.modules.auth.models import User

    admin = db.execute(
        select(User.id).where(User.tenant_id == parse_uuid(str(tenant_id)), User.role == "admin")
    ).scalar_one_or_none()
    if admin:
        return admin
    any_user = db.execute(
        select(User.id).where(User.tenant_id == parse_uuid(str(tenant_id)))
    ).scalar_one_or_none()  # noqa: E501
    return any_user


def ensure_project_channel(db: Session, placement) -> Channel | None:
    """#proyek-{klien} untuk karyawan outsourcing + tim Ops proyeknya."""
    try:
        from app.modules.clients.models import Client
        from app.modules.hrd.models import Employee
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
        creator_id = _get_admin_user_id(db, placement.tenant_id) or placement.tenant_id
        if existing:
            # Ensure new worker is added if not already
            worker = db.execute(
                select(Employee.user_id)
                .where(Employee.placement_id == placement.id)
                .where(Employee.user_id.is_not(None))  # noqa: E501
            ).scalar_one_or_none()
            if worker and not _is_member(db, existing.id, worker):
                db.add(
                    ChatChannelMember(
                        channel_id=existing.id, user_id=worker, tenant_id=placement.tenant_id
                    )
                )  # noqa: E501
                db.commit()
            return existing
        ch = Channel(
            tenant_id=placement.tenant_id,
            name=f"Proyek: {client.name}",
            slug=slug,
            channel_type="private",
            created_by_id=creator_id,
        )
        db.add(ch)
        db.flush()
        for uid in _get_ops_user_ids(db, placement.tenant_id):
            db.add(ChatChannelMember(channel_id=ch.id, user_id=uid, tenant_id=placement.tenant_id))
        # Tambah pekerja yang baru ditempatkan
        worker = db.execute(
            select(Employee.user_id)
            .where(Employee.placement_id == placement.id)
            .where(Employee.user_id.is_not(None))  # noqa: E501
        ).scalar_one_or_none()
        if worker and worker not in _get_ops_user_ids(db, placement.tenant_id):
            db.add(
                ChatChannelMember(channel_id=ch.id, user_id=worker, tenant_id=placement.tenant_id)
            )  # noqa: E501
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
        creator_id = _get_admin_user_id(db, run.tenant_id) or run.tenant_id
        ch = Channel(
            tenant_id=run.tenant_id,
            name=f"Payroll {run.month}/{run.year}",
            slug=slug,
            channel_type="private",
            created_by_id=creator_id,
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
    ch.total_msg_count += 1
    db.commit()
    _notify_channel(db, ch, "message.created")


# ---------- Mention & Search (PRD sisa) ----------


def search_messages(
    db: Session, user, q: str, channel_id: str | None = None, limit: int = 20
) -> list[dict]:  # noqa: E501
    """Pencarian pesan: full-text search di Postgres (index GIN, ada ranking),
    ILIKE di SQLite dev/test (tidak ada FTS bawaan)."""

    q_clean = q.strip()
    if not q_clean or len(q_clean) < 2:
        return []
    # Tentukan channel yang boleh dibaca
    if channel_id:
        ch = get_channel_with_access_check(db, user, channel_id)
        allowed_ids = [ch.id]
    else:
        raw_ids = [c["id"] for c in list_channels(db, user)]
        allowed_ids = [uid for cid in raw_ids if (uid := parse_uuid(str(cid))) is not None]  # type: ignore[assignment]
        if not allowed_ids:
            return []

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        msgs = _search_messages_fts(db, allowed_ids, q_clean, limit)
    else:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.channel_id.in_(allowed_ids))
            .where(ChatMessage.deleted_at.is_(None))
            .where(ChatMessage.content.ilike(f"%{q_clean}%"))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        msgs = list(db.execute(stmt).scalars().all())
    return [_serialize_message(m, user.id) for m in msgs]


def _search_messages_fts(db: Session, channel_ids: list, q: str, limit: int) -> list[ChatMessage]:
    """Full-text search via `to_tsvector('simple', content) @@ websearch_to_tsquery(...)`,
    dibantu index GIN `ix_chat_messages_search_fts` (migrasi 600bd504ad4e).
    `websearch_to_tsquery` dipilih (bukan `to_tsquery`) karena mentolerir
    input bebas dari kotak cari (tanda baca ganjil, dst.) tanpa error.
    """
    stmt = text(
        """
        SELECT id FROM chat_messages
        WHERE channel_id IN :channel_ids
          AND deleted_at IS NULL
          AND to_tsvector('simple', content) @@ websearch_to_tsquery('simple', :q)
        ORDER BY ts_rank(to_tsvector('simple', content), websearch_to_tsquery('simple', :q)) DESC
        LIMIT :limit
        """
    ).bindparams(bindparam("channel_ids", expanding=True))
    rows = db.execute(
        stmt, {"channel_ids": [str(cid) for cid in channel_ids], "q": q, "limit": limit}
    ).all()
    ordered_ids = [parse_uuid(r.id) for r in rows]
    if not ordered_ids:
        return []
    by_id = {
        m.id: m
        for m in db.execute(
            select(ChatMessage)
            .options(joinedload(ChatMessage.reactions), joinedload(ChatMessage.files))
            .where(ChatMessage.id.in_(ordered_ids))
        )
        .unique()
        .scalars()
    }
    return [by_id[i] for i in ordered_ids if i in by_id]


def search_users_for_mention(db: Session, user, q: str, limit: int = 10) -> list[dict]:
    """Autocomplete mention: staff melihat semua, karyawan hanya cohort + Ops."""
    from app.modules.auth.models import User

    q_clean = q.strip().lower()
    if not q_clean:
        return []
    # Tentukan user yang boleh di-mention
    if is_staff(user):
        stmt = select(User).where(User.tenant_id == user.tenant_id, User.is_active.is_(True))
        if q_clean:
            stmt = stmt.where(
                (User.full_name.ilike(f"%{q_clean}%")) | (User.email.ilike(f"%{q_clean}%"))
            )
        users = list(db.execute(stmt.limit(limit)).scalars().all())
    else:
        # Karyawan: cohort = sesama karyawan se-proyek + tim Ops
        ops_ids = set(_get_ops_user_ids(db, user.tenant_id))
        # Cari placement karyawan sendiri
        from app.modules.hrd.models import Employee
        from app.modules.recruitment.models import JobOrder, Placement

        emp = db.execute(select(Employee).where(Employee.user_id == user.id)).scalar_one_or_none()
        cohort_ids: set = set(ops_ids)
        if emp and emp.placement_id:
            placement = db.get(Placement, emp.placement_id)
            if placement:
                jo = db.get(JobOrder, placement.job_order_id)
                if jo:
                    # Semua karyawan ditempatkan di klien yang sama
                    cohort_emps = (
                        db.execute(
                            select(Employee.user_id)
                            .join(Placement, Employee.placement_id == Placement.id)
                            .join(JobOrder, Placement.job_order_id == JobOrder.id)
                            .where(JobOrder.client_id == jo.client_id)
                            .where(Employee.user_id.is_not(None))
                        )
                        .scalars()
                        .all()
                    )
                    cohort_ids.update(cohort_emps)
        if not cohort_ids:
            return []
        stmt = select(User).where(User.id.in_(cohort_ids), User.is_active.is_(True))
        if q_clean:
            stmt = stmt.where(
                (User.full_name.ilike(f"%{q_clean}%")) | (User.email.ilike(f"%{q_clean}%"))
            )
        users = list(db.execute(stmt.limit(limit)).scalars().all())
    return [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email, "role": u.role.value}
        for u in users
    ]


def _validate_mentions(db: Session, user, channel_id: str, content: str) -> None:
    """Tolak pesan jika menyebut user di luar scope (karyawan only)."""
    if is_staff(user) or "@" not in content:
        return
    mentions = _extract_mention_tokens(content)
    if not mentions:
        return
    allowed = {u["id"]: u for u in search_users_for_mention(db, user, "", limit=1000)}
    # Juga izinkan @channel/@here untuk karyawan (broadcast)
    for raw in mentions:
        name = raw.strip().lower()
        if name in ("channel", "here", "all"):
            continue
        # Cari user dengan nama mengandung mention
        matched = [
            u
            for u in allowed.values()
            if name in u["full_name"].lower() or name in u["email"].lower()
        ]  # noqa: E501
        if not matched:
            raise HTTPException(status_code=403, detail=f"Mention @{raw} di luar scope proyek Anda")
