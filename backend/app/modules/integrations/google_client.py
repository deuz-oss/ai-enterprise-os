"""Adapter Google OAuth + Gmail + Calendar untuk sync Activity lead.

Catatan implementasi: skema endpoint mengikuti Google OAuth2/Gmail API v1/
Calendar API v3 yang didokumentasikan publik. Semua kegagalan jaringan
dipetakan ke HTTPException 502 (pola sama `core/esign/privy.py`). Belum
pernah diuji terhadap kredensial Google produksi sungguhan -- OAuth app
harus didaftarkan sendiri di Google Cloud Console (di luar cakupan kode
ini), tes otomatis di sini memvalidasi logika lewat HTTP call yang di-mock.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# read-only cukup untuk sync satu arah (baca & catat, tidak pernah kirim/ubah
# apa pun di akun Google staf) -- prinsip least privilege.
SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/userinfo.email"
)


def _require_configured() -> None:
    settings = get_settings()
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Integrasi Google belum dikonfigurasi -- admin perlu mengisi "
                "GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI"
            ),
        )


def build_authorize_url(*, state: str) -> str:
    """URL consent screen Google -- `access_type=offline` + `prompt=consent`
    supaya `refresh_token` selalu dikirim (tanpa ini Google cuma kirim
    refresh_token di izin PERTAMA kali, tidak di re-consent berikutnya)."""
    _require_configured()
    settings = get_settings()
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Tukar authorization code -> access_token + refresh_token."""
    _require_configured()
    settings = get_settings()
    try:
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Google token exchange HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
        )
        raise HTTPException(status_code=502, detail="Google menolak kode otorisasi") from exc
    except httpx.HTTPError as exc:
        logger.error("Google token exchange gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menghubungi Google") from exc


def refresh_access_token(refresh_token: str) -> dict:
    _require_configured()
    settings = get_settings()
    try:
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Google token refresh HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
        )
        raise HTTPException(
            status_code=502, detail="Google menolak refresh token -- perlu hubungkan ulang akun"
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Google token refresh gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menghubungi Google") from exc


def fetch_userinfo(access_token: str) -> dict:
    try:
        resp = httpx.get(
            _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Google userinfo gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal mengambil profil akun Google") from exc


def list_gmail_messages(access_token: str, *, query: str, max_results: int = 25) -> list[dict]:
    """Daftar ringkas (id saja) -- panggil `get_gmail_message` per id untuk
    detail (subjek, snippet, tanggal)."""
    try:
        resp = httpx.get(
            _GMAIL_MESSAGES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": query, "maxResults": max_results},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("messages", [])
    except httpx.HTTPError as exc:
        logger.error("Gmail messages.list gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal mengambil daftar email Gmail") from exc


def get_gmail_message(access_token: str, message_id: str) -> dict:
    try:
        resp = httpx.get(
            f"{_GMAIL_MESSAGES_URL}/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Gmail messages.get gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal mengambil detail email Gmail") from exc


def list_calendar_events(access_token: str, *, query: str, time_min: datetime) -> list[dict]:
    try:
        resp = httpx.get(
            _CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "q": query,
                "timeMin": time_min.astimezone(UTC).isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 25,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
    except httpx.HTTPError as exc:
        logger.error("Calendar events.list gagal: %s", exc)
        raise HTTPException(
            status_code=502, detail="Gagal mengambil jadwal Google Calendar"
        ) from exc


def is_token_expired(expires_at: datetime, *, skew_seconds: int = 60) -> bool:
    if expires_at.tzinfo is None:  # SQLite menyimpan naive (pola sama modul lain)
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) >= (expires_at - timedelta(seconds=skew_seconds))


def token_expiry_from_expires_in(expires_in: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=expires_in)
