import logging
import smtplib
import threading
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import parse_uuid
from app.modules.auth.models import User, UserRole
from app.modules.notifications.models import Notification

logger = logging.getLogger(__name__)


def build_email_message(to: str, subject: str, body: str) -> EmailMessage:
    """Susun pesan email notifikasi (fungsi murni agar mudah dites)."""
    msg = EmailMessage()
    msg["Subject"] = f"[AEOS] {subject}"
    msg["From"] = get_settings().smtp_from or get_settings().smtp_user or "aeos@localhost"
    msg["To"] = to
    footer = (
        "\n\n--\nPesan ini dikirim otomatis oleh AI Enterprise OS. "
        "Balas lewat portal atau hubungi HR."
    )
    msg.set_content((body or subject) + footer)
    return msg


def _smtp_send(msg: EmailMessage) -> None:
    """Kirim pesan lewat SMTP; kegagalan hanya dicatat ke log."""
    settings = get_settings()
    host = settings.smtp_host
    if not host:
        return
    try:
        port = settings.smtp_port
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or "")
                smtp.send_message(msg)
    except Exception:  # noqa: BLE001 - email tidak boleh mematahkan bisnis
        logger.exception("Gagal mengirim email notifikasi ke %s", msg["To"])


def send_raw_email(to: str, subject: str, body: str) -> None:
    """Kirim email langsung ke alamat manapun (bukan user in-app) — dipakai
    alur yang belum tentu punya konteks user login, mis. forgot-password.
    No-op senyap bila SMTP tak dikonfigurasi (sama seperti `_smtp_send`).
    """
    _smtp_send(build_email_message(to, subject, body))


def _queue_email(db: Session, user_id, title: str, body: str | None) -> None:
    """Antre email notifikasi bila SMTP diatur; pengiriman di thread terpisah."""
    settings = get_settings()
    if not settings.email_enabled:
        return
    recipient = db.execute(
        select(User.email).where(User.id == parse_uuid(str(user_id)))
    ).scalar_one_or_none()
    if not recipient:
        return
    msg = build_email_message(recipient, title, body or "")
    threading.Thread(target=_smtp_send, args=(msg,), daemon=True).start()


def notify(
    db: Session,
    *,
    user_id,
    title: str,
    body: str | None = None,
    category: str = "leave",
    entity_type: str | None = None,
    entity_id=None,
) -> None:
    """Kirim satu notifikasi in-app; gagal mencatat tidak mematahkan bisnis."""
    try:
        db.add(
            Notification(
                user_id=parse_uuid(str(user_id)),
                title=title[:200],
                body=body[:500] if body else None,
                category=category,
                entity_type=entity_type,
                entity_id=parse_uuid(str(entity_id)) if entity_id else None,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - notifikasi tidak boleh mematahkan bisnis
        logger.exception("Gagal mengirim notifikasi user=%s", user_id)
        db.rollback()
        return
    # Notifikasi in-app tersimpan → teruskan ke email bila fitur aktif.
    _queue_email(db, user_id, title, body)


def notify_hr_users(db: Session, *, title: str, body: str | None, entity_id=None) -> int:
    """Beri tahu semua admin & HR aktif dalam tenant yang sedang aktif."""
    from app.core.tenancy import get_tenant

    tenant_id = get_tenant()
    if tenant_id is None:
        return 0
    recipients = (
        db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.hr]),
            )
        )
        .scalars()
        .all()
    )
    for uid in recipients:
        notify(
            db,
            user_id=uid,
            title=title,
            body=body,
            category="leave",
            entity_type="leave_request",
            entity_id=entity_id,
        )
    return len(recipients)


def list_own(db: Session, user, unread_only: bool = False) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return list(db.execute(stmt).scalars())


def unread_count(db: Session, user) -> int:
    return int(
        db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
            )
        ).scalar()
        or 0
    )


def mark_read(db: Session, user, notification_id: str) -> Notification:
    notification = db.get(Notification, parse_uuid(notification_id))
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    if notification.read_at is None:
        from datetime import UTC, datetime

        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user) -> int:
    """Tandai semua notifikasi milik user sebagai dibaca; kembalikan jumlahnya."""
    from datetime import UTC, datetime

    unread = list(
        db.execute(
            select(Notification).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        ).scalars()
    )
    now = datetime.now(UTC)
    for notification in unread:
        notification.read_at = now
    if unread:
        db.commit()
    return len(unread)
