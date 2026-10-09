"""Revokasi token JWT saat password berubah (users.token_version + klaim `tv`)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import ALGORITHM
from starlette.websockets import WebSocketDisconnect

from tests.conftest import _auth_header, _login_header

EMAIL = "revokasi@example.com"


def _register(client, admin_headers):
    resp = client.post(
        "/api/v1/auth/register",
        headers=admin_headers,
        json={"email": EMAIL, "full_name": "Revokasi", "password": "password123", "role": "hr"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _me(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).status_code


def _legacy_token(user_id: str, **extra) -> str:
    """Token berformat lama (tanpa klaim `tv`), seperti yang terbit sebelum rilis ini."""
    payload = {"sub": user_id, "exp": datetime.now(UTC) + timedelta(minutes=30), **extra}
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def test_change_password_revokes_other_sessions_and_returns_new_token(client):
    admin = _auth_header(client)
    _register(client, admin)
    laptop = _login_header(client, EMAIL, "password123")
    phone = _login_header(client, EMAIL, "password123")

    resp = client.post(
        "/api/v1/auth/change-password",
        headers=laptop,
        json={"old_password": "password123", "new_password": "password456"},
    )
    assert resp.status_code == 200, resp.text
    fresh = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    assert _me(client, laptop) == 401
    assert _me(client, phone) == 401
    assert _me(client, fresh) == 200


def test_reset_password_via_token_revokes_existing_sessions(client):
    admin = _auth_header(client)
    user_id = _register(client, admin)
    stolen = _login_header(client, EMAIL, "password123")

    reset = client.post(f"/api/v1/auth/users/{user_id}/password-reset-token", headers=admin)
    assert reset.status_code == 200, reset.text
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset.json()["reset_token"], "new_password": "password789"},
    )
    assert resp.status_code == 200, resp.text

    assert _me(client, stolen) == 401
    assert _me(client, _login_header(client, EMAIL, "password789")) == 200


def test_admin_setting_password_revokes_user_sessions(client):
    admin = _auth_header(client)
    user_id = _register(client, admin)
    session = _login_header(client, EMAIL, "password123")

    resp = client.patch(
        f"/api/v1/auth/users/{user_id}", headers=admin, json={"new_password": "password999"}
    )
    assert resp.status_code == 200, resp.text
    assert _me(client, session) == 401
    # Mengubah data lain (tanpa password) TIDAK mencabut sesi.
    session = _login_header(client, EMAIL, "password999")
    resp = client.patch(f"/api/v1/auth/users/{user_id}", headers=admin, json={"full_name": "Baru"})
    assert resp.status_code == 200, resp.text
    assert _me(client, session) == 200
    # Sesi admin sendiri tidak terpengaruh.
    assert _me(client, admin) == 200


def test_legacy_token_without_claim_stays_valid_until_password_changes(client):
    """Rilis ini tidak memaksa semua user logout: token tanpa `tv` = versi 0."""
    admin = _auth_header(client)
    user_id = _register(client, admin)
    legacy = {"Authorization": f"Bearer {_legacy_token(user_id)}"}
    assert _me(client, legacy) == 200

    fresh = _login_header(client, EMAIL, "password123")
    client.post(
        "/api/v1/auth/change-password",
        headers=fresh,
        json={"old_password": "password123", "new_password": "password456"},
    )
    assert _me(client, legacy) == 401


@pytest.mark.parametrize("bad_claim", ["0", None, 1.0, True])
def test_malformed_version_claim_is_rejected(client, bad_claim):
    admin = _auth_header(client)
    user_id = _register(client, admin)
    token = _legacy_token(user_id, tv=bad_claim)
    assert _me(client, {"Authorization": f"Bearer {token}"}) == 401


def test_repeated_logins_do_not_revoke_each_other(client):
    admin = _auth_header(client)
    _register(client, admin)
    first = _login_header(client, EMAIL, "password123")
    second = _login_header(client, EMAIL, "password123")
    assert _me(client, first) == 200
    assert _me(client, second) == 200


def test_chat_websocket_rejects_revoked_token(client, monkeypatch):
    # WS membuka SessionLocal() sendiri (di luar DI) -- arahkan ke DB test.
    import app.core.database as database

    monkeypatch.setattr(database, "SessionLocal", client.testing_session)
    admin = _auth_header(client)
    _register(client, admin)
    old = _login_header(client, EMAIL, "password123")["Authorization"].split()[1]

    # Kontrol positif: token valid tersambung.
    with client.websocket_connect(f"/api/v1/chat/ws?token={old}"):
        pass

    resp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old}"},
        json={"old_password": "password123", "new_password": "password456"},
    )
    assert resp.status_code == 200, resp.text
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/chat/ws?token={old}"):
            pass
    assert exc.value.code == 1008
