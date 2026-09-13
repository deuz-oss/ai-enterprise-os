from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import parse_uuid
from app.core.tenancy import set_tenant
from app.modules.integrations import google_client
from app.modules.integrations.models import GoogleMailboxConnection
from app.modules.integrations.schemas import GoogleSyncResultOut
from app.modules.presales.models import ActivityType, Lead, LeadActivity

logger = logging.getLogger(__name__)

_STATE_PURPOSE = "google_oauth_state"
_STATE_TTL_MINUTES = 10
_STATE_ALGORITHM = "HS256"
_DEFAULT_SYNC_WINDOW_DAYS = 90


def _get_connection(db: Session, user_id) -> GoogleMailboxConnection | None:
    return db.execute(
        select(GoogleMailboxConnection).where(GoogleMailboxConnection.user_id == user_id)
    ).scalar_one_or_none()


def build_authorize_url(user) -> str:
    """`state` bawa identitas user + tenant lewat JWT bertanda tangan (pola
    sama `security.create_access_token`) -- dipakai lagi saat callback
    karena Google me-redirect browser TANPA header Authorization kita,
    jadi `TenantContextMiddleware` normal tidak sempat mengisi konteks
    tenant untuk request itu (harus diisi manual, lihat `handle_callback`)."""
    settings = get_settings()
    state = jwt.encode(
        {
            "sub": str(user.id),
            "tid": str(user.tenant_id),
            "purpose": _STATE_PURPOSE,
            "exp": datetime.now(UTC) + timedelta(minutes=_STATE_TTL_MINUTES),
        },
        settings.secret_key,
        algorithm=_STATE_ALGORITHM,
    )
    return google_client.build_authorize_url(state=state)


def _decode_state(state: str) -> tuple[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[_STATE_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=400, detail="State OAuth tidak valid atau kedaluwarsa"
        ) from exc
    if payload.get("purpose") != _STATE_PURPOSE or not payload.get("sub") or not payload.get("tid"):
        raise HTTPException(status_code=400, detail="State OAuth tidak valid")
    return str(payload["sub"]), str(payload["tid"])


def handle_callback(db: Session, *, code: str, state: str) -> GoogleMailboxConnection:
    user_id_raw, tenant_id_raw = _decode_state(state)
    user_id = parse_uuid(user_id_raw)
    # Request ini tidak lewat `TenantContextMiddleware` yang normal (tidak
    # ada header Authorization dari redirect Google) -- isi konteks tenant
    # manual dari `state` sebelum menulis apa pun, supaya `before_flush`
    # tenancy.py bisa mengisi `tenant_id` baris baru & RLS Postgres benar.
    set_tenant(parse_uuid(tenant_id_raw))
    tokens = google_client.exchange_code_for_tokens(code)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    if not access_token:
        raise HTTPException(status_code=502, detail="Google tidak mengembalikan access_token")

    userinfo = google_client.fetch_userinfo(access_token)
    google_email = userinfo.get("email", "")
    expires_at = google_client.token_expiry_from_expires_in(expires_in)

    connection = _get_connection(db, user_id)
    if connection is None:
        if not refresh_token:
            raise HTTPException(
                status_code=502,
                detail="Google tidak mengirim refresh_token -- coba hubungkan ulang akun",
            )
        connection = GoogleMailboxConnection(
            id=uuid4(),
            user_id=user_id,
            google_email=google_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
        )
        db.add(connection)
    else:
        connection.google_email = google_email
        connection.access_token = access_token
        # Google cuma kirim refresh_token lagi kalau `prompt=consent` --
        # kita selalu pakai itu (lihat google_client.build_authorize_url),
        # tapi tetap jaga-jaga tidak menimpa dengan None kalau suatu saat
        # Google tidak mengirimnya.
        if refresh_token:
            connection.refresh_token = refresh_token
        connection.token_expires_at = expires_at
    db.commit()
    db.refresh(connection)
    return connection


def get_status(db: Session, user) -> GoogleMailboxConnection | None:
    return _get_connection(db, user.id)


def disconnect(db: Session, user) -> None:
    connection = _get_connection(db, user.id)
    if connection is not None:
        db.delete(connection)
        db.commit()


def _valid_access_token(db: Session, connection: GoogleMailboxConnection) -> str:
    if not google_client.is_token_expired(connection.token_expires_at):
        return connection.access_token
    tokens = google_client.refresh_access_token(connection.refresh_token)
    connection.access_token = tokens["access_token"]
    connection.token_expires_at = google_client.token_expiry_from_expires_in(
        tokens.get("expires_in", 3600)
    )
    db.commit()
    return connection.access_token


def _lead_contact_emails(lead: Lead) -> list[str]:
    """Prioritaskan kontak yang eksplisit ditautkan lewat `LeadContact`
    (Fase 40); fallback ke `primary_contact` company-level untuk lead lama
    yang belum pernah pakai fitur itu."""
    emails = {lc.contact.email for lc in lead.lead_contacts if lc.contact.email}
    if not emails and lead.primary_contact and lead.primary_contact.email:
        emails.add(lead.primary_contact.email)
    return sorted(emails)


def _parse_event_start(event: dict) -> datetime | None:
    start = event.get("start", {})
    raw = start.get("dateTime") or start.get("date")
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _sync_gmail(
    db: Session, lead: Lead, access_token: str, emails: list[str], since: datetime
) -> int:
    query = (
        " OR ".join(f"(from:{e} OR to:{e})" for e in emails) + f" after:{int(since.timestamp())}"
    )
    imported = 0
    for msg in google_client.list_gmail_messages(access_token, query=query):
        message_id = msg["id"]
        existing = db.execute(
            select(LeadActivity).where(
                LeadActivity.external_source == "gmail", LeadActivity.external_id == message_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        detail = google_client.get_gmail_message(access_token, message_id)
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject") or "(tanpa subjek)"
        sender = headers.get("From")
        content = f"{subject} -- dari {sender}" if sender else subject
        db.add(
            LeadActivity(
                lead_id=lead.id,
                activity_type=ActivityType.email,
                content=content,
                external_source="gmail",
                external_id=message_id,
            )
        )
        imported += 1
    return imported


def _sync_calendar(
    db: Session, lead: Lead, access_token: str, emails: list[str], since: datetime
) -> int:
    imported = 0
    seen_ids: set[str] = set()
    for email in emails:
        for event in google_client.list_calendar_events(access_token, query=email, time_min=since):
            event_id = event["id"]
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            existing = db.execute(
                select(LeadActivity).where(
                    LeadActivity.external_source == "google_calendar",
                    LeadActivity.external_id == event_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            db.add(
                LeadActivity(
                    lead_id=lead.id,
                    activity_type=ActivityType.meeting,
                    content=event.get("summary") or "(tanpa judul)",
                    due_at=_parse_event_start(event),
                    external_source="google_calendar",
                    external_id=event_id,
                )
            )
            imported += 1
    return imported


def sync_lead(db: Session, *, user, lead: Lead) -> GoogleSyncResultOut:
    connection = _get_connection(db, user.id)
    if connection is None:
        raise HTTPException(status_code=422, detail="Hubungkan akun Google Anda dulu")
    emails = _lead_contact_emails(lead)
    if not emails:
        raise HTTPException(
            status_code=422,
            detail="Lead ini belum punya kontak dengan email -- tidak ada yang bisa disinkronkan",
        )
    access_token = _valid_access_token(db, connection)

    now = datetime.now(UTC)
    since = connection.last_synced_at or (now - timedelta(days=_DEFAULT_SYNC_WINDOW_DAYS))
    if since.tzinfo is None:  # SQLite menyimpan naive (pola sama modul lain)
        since = since.replace(tzinfo=UTC)

    emails_imported = _sync_gmail(db, lead, access_token, emails, since)
    events_imported = _sync_calendar(db, lead, access_token, emails, since)

    connection.last_synced_at = now
    if emails_imported or events_imported:
        lead.last_activity_at = now
    db.commit()

    return GoogleSyncResultOut(
        emails_imported=emails_imported, events_imported=events_imported, synced_at=now
    )
