"""Fase 47 -- sync Gmail/Google Calendar. Google API dipanggil lewat
`app.modules.integrations.google_client`, jadi tes ini mock fungsi-fungsi
di modul itu (bukan httpx transport mentah) -- pola sama
`app.modules.notifications.service.send_raw_email_with_attachment` yang
sudah dipakai di test_presales.py. Tidak ada tes yang benar-benar
menghubungi Google -- kredensial OAuth produksi tidak tersedia di CI/dev
sandbox ini.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings

from tests.conftest import _auth_header


def _configure_google(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_oauth_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "google_oauth_redirect_uri",
        "http://localhost:8000/api/v1/integrations/google/callback",
    )


def _extract_state(authorize_url: str) -> str:
    return parse_qs(urlparse(authorize_url).query)["state"][0]


def test_authorize_requires_configuration(client):
    headers = _auth_header(client)
    resp = client.get("/api/v1/integrations/google/authorize", headers=headers)
    assert resp.status_code == 503


def test_authorize_returns_consent_url_when_configured(client, monkeypatch):
    _configure_google(monkeypatch)
    headers = _auth_header(client)
    resp = client.get("/api/v1/integrations/google/authorize", headers=headers)
    assert resp.status_code == 200, resp.text
    url = resp.json()["authorize_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    params = parse_qs(urlparse(url).query)
    assert params["client_id"][0] == "test-client-id"
    assert params["access_type"][0] == "offline"
    assert "gmail.readonly" in params["scope"][0]


def test_callback_rejects_invalid_state(client, monkeypatch):
    _configure_google(monkeypatch)
    resp = client.get(
        "/api/v1/integrations/google/callback",
        params={"code": "irrelevant", "state": "bukan-jwt-valid"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_callback_creates_connection_and_status_reflects_it(client, monkeypatch):
    _configure_google(monkeypatch)
    headers = _auth_header(client)
    authorize_url = client.get("/api/v1/integrations/google/authorize", headers=headers).json()[
        "authorize_url"
    ]
    state = _extract_state(authorize_url)

    with (
        patch(
            "app.modules.integrations.service.google_client.exchange_code_for_tokens",
            return_value={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
        ),
        patch(
            "app.modules.integrations.service.google_client.fetch_userinfo",
            return_value={"email": "staf@gmail.com"},
        ),
    ):
        callback_resp = client.get(
            "/api/v1/integrations/google/callback",
            params={"code": "auth-code-1", "state": state},
            follow_redirects=False,
        )
    assert callback_resp.status_code in (302, 307), callback_resp.text
    assert "leads?google_connected=1" in callback_resp.headers["location"]

    status = client.get("/api/v1/integrations/google/status", headers=headers).json()
    assert status["connected"] is True
    assert status["google_email"] == "staf@gmail.com"


def _connect_google(client, headers, monkeypatch, email="staf@gmail.com"):
    _configure_google(monkeypatch)
    authorize_url = client.get("/api/v1/integrations/google/authorize", headers=headers).json()[
        "authorize_url"
    ]
    state = _extract_state(authorize_url)
    with (
        patch(
            "app.modules.integrations.service.google_client.exchange_code_for_tokens",
            return_value={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
        ),
        patch(
            "app.modules.integrations.service.google_client.fetch_userinfo",
            return_value={"email": email},
        ),
    ):
        client.get(
            "/api/v1/integrations/google/callback",
            params={"code": "auth-code-1", "state": state},
            follow_redirects=False,
        )


def test_status_disconnected_by_default(client):
    headers = _auth_header(client)
    status = client.get("/api/v1/integrations/google/status", headers=headers).json()
    assert status["connected"] is False


def test_disconnect_removes_connection(client, monkeypatch):
    headers = _auth_header(client)
    _connect_google(client, headers, monkeypatch)
    assert (
        client.get("/api/v1/integrations/google/status", headers=headers).json()["connected"]
        is True
    )

    deleted = client.delete("/api/v1/integrations/google/connection", headers=headers)
    assert deleted.status_code == 204
    assert (
        client.get("/api/v1/integrations/google/status", headers=headers).json()["connected"]
        is False
    )


def test_sync_lead_requires_connection(client):
    headers = _auth_header(client)
    lead = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"company_name": "PT Sync Tanpa Koneksi", "contact_email": "pic@sync.co.id"},
    ).json()
    resp = client.post(f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers)
    assert resp.status_code == 422


def test_sync_lead_requires_contact_email(client, monkeypatch):
    headers = _auth_header(client)
    _connect_google(client, headers, monkeypatch)
    lead = client.post(
        "/api/v1/leads", headers=headers, json={"company_name": "PT Tanpa Email"}
    ).json()
    resp = client.post(f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers)
    assert resp.status_code == 422


def test_sync_lead_imports_email_and_calendar_event(client, monkeypatch):
    headers = _auth_header(client)
    _connect_google(client, headers, monkeypatch)
    lead = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"company_name": "PT Sync Lengkap", "contact_email": "pic@synclengkap.co.id"},
    ).json()

    gmail_message_detail = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Penawaran Harga"},
                {"name": "From", "value": "pic@synclengkap.co.id"},
            ]
        }
    }
    calendar_event = {
        "id": "evt-1",
        "summary": "Meeting kickoff",
        "start": {"dateTime": "2026-12-01T10:00:00+07:00"},
    }
    with (
        patch(
            "app.modules.integrations.service.google_client.list_gmail_messages",
            return_value=[{"id": "msg-1"}],
        ),
        patch(
            "app.modules.integrations.service.google_client.get_gmail_message",
            return_value=gmail_message_detail,
        ),
        patch(
            "app.modules.integrations.service.google_client.list_calendar_events",
            return_value=[calendar_event],
        ),
    ):
        resp = client.post(f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["emails_imported"] == 1
    assert body["events_imported"] == 1

    activities = client.get(f"/api/v1/leads/{lead['id']}/activities", headers=headers).json()
    assert len(activities) == 2
    email_activity = next(a for a in activities if a["activity_type"] == "email")
    assert "Penawaran Harga" in email_activity["content"]
    meeting_activity = next(a for a in activities if a["activity_type"] == "meeting")
    assert meeting_activity["content"] == "Meeting kickoff"
    assert meeting_activity["due_at"] is not None


def test_sync_lead_dedupes_on_repeat_sync(client, monkeypatch):
    headers = _auth_header(client)
    _connect_google(client, headers, monkeypatch)
    lead = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"company_name": "PT Sync Dedup", "contact_email": "pic@syncdedup.co.id"},
    ).json()

    with (
        patch(
            "app.modules.integrations.service.google_client.list_gmail_messages",
            return_value=[{"id": "msg-dedup"}],
        ),
        patch(
            "app.modules.integrations.service.google_client.get_gmail_message",
            return_value={"payload": {"headers": [{"name": "Subject", "value": "Follow up"}]}},
        ),
        patch(
            "app.modules.integrations.service.google_client.list_calendar_events",
            return_value=[],
        ),
    ):
        first = client.post(
            f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers
        ).json()
        second = client.post(
            f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers
        ).json()

    assert first["emails_imported"] == 1
    assert second["emails_imported"] == 0
    activities = client.get(f"/api/v1/leads/{lead['id']}/activities", headers=headers).json()
    assert len(activities) == 1


def test_sync_lead_refreshes_expired_token(client, monkeypatch):
    headers = _auth_header(client)
    _connect_google(client, headers, monkeypatch)

    # Paksa token dianggap kedaluwarsa dengan mundurkan token_expires_at
    # langsung di DB lewat sesi test yang sama.
    from app.modules.integrations.models import GoogleMailboxConnection

    db = client.testing_session()
    try:
        conn = db.query(GoogleMailboxConnection).first()
        conn.token_expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    lead = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"company_name": "PT Refresh Token", "contact_email": "pic@refresh.co.id"},
    ).json()

    with (
        patch(
            "app.modules.integrations.service.google_client.refresh_access_token",
            return_value={"access_token": "at-refreshed", "expires_in": 3600},
        ) as mocked_refresh,
        patch(
            "app.modules.integrations.service.google_client.list_gmail_messages", return_value=[]
        ),
        patch(
            "app.modules.integrations.service.google_client.list_calendar_events", return_value=[]
        ),
    ):
        resp = client.post(f"/api/v1/integrations/google/sync/{lead['id']}", headers=headers)
    assert resp.status_code == 200, resp.text
    mocked_refresh.assert_called_once()
