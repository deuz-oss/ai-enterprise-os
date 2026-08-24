"""Test keamanan lanjutan: ganti/reset password, rate limit login, token reset."""

from unittest.mock import patch

from app.core.config import get_settings
from app.core.ratelimit import reset_all_limiters

from tests.conftest import _auth_header, _login_header


def _register(client, headers, email, role="hr"):
    resp = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "password": "password123",
            "role": role,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_change_password_sendiri(client):
    admin = _auth_header(client)
    user = _register(client, admin, "ganti-pass@example.com")
    headers = _login_header(client, "ganti-pass@example.com", "password123")

    # Password lama salah → ditolak
    bad = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "bukan-lama", "new_password": "password456"},
    )
    assert bad.status_code == 422

    ok = client.post(
        "/api/v1/auth/change-password", headers=headers,
        json={"old_password": "password123", "new_password": "password456"},
    )
    assert ok.status_code == 204

    # Login dengan password lama gagal; baru berhasil
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "ganti-pass@example.com", "password": "password123"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "ganti-pass@example.com", "password": "password456"},
    )
    assert new_login.status_code == 200

    # Event audit tercatat (baca via admin; role hr tak boleh baca audit)
    logs = client.get(
        "/api/v1/audit/logs",
        headers=admin,
        params={"action_prefix": "auth.password_changed"},
    ).json()
    assert logs["total"] == 1
    assert user["id"] == logs["items"][0]["entity_id"]


def test_reset_password_alur_admin_token(client):
    admin = _auth_header(client)
    user = _register(client, admin, "reset-target@example.com")

    issued = client.post(
        f"/api/v1/auth/users/{user['id']}/password-reset-token", headers=admin
    )
    assert issued.status_code == 200
    token = issued.json()["reset_token"]
    assert len(token) > 20

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "password789"},
    )
    assert reset.status_code == 200

    # Token lama tak bisa dipakai lagi (satu kali pakai)
    reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "password000"},
    )
    assert reuse.status_code == 422

    # Login pakai password baru
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset-target@example.com", "password": "password789"},
    )
    assert login.status_code == 200


def test_reset_token_tidak_valid_atau_kedaluwarsa(client):
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "token-ngasal", "new_password": "password123"},
    )
    assert resp.status_code == 422


def test_reset_token_lintas_tenant_ditolak_admin_lain(client):
    from tests.conftest import _platform_admin_header as plat

    prov = client.post(
        "/api/v1/platform/tenants",
        headers=plat(client),
        json={
            "name": "T Alpha",
            "slug": "alpha-sec",
            "admin_email": "admin-alpha-sec@example.com",
            "admin_password": "password123",
            "admin_full_name": "A",
        },
    ).json()
    alpha = _login_header(client, "admin-alpha-sec@example.com", "password123")
    target = _register(client, alpha, "anggota-alpha@example.com")

    # Admin default tenant mencoba reset user tenant alpha → 404 (terfilter)
    denied = client.post(
        f"/api/v1/auth/users/{target['id']}/password-reset-token",
        headers=_auth_header(client),
    )
    assert denied.status_code == 404
    del prov


def test_rate_limit_login(client):
    settings = get_settings()
    reset_all_limiters()
    # Seed admin SEBELUM percobaan diblokir agar email dikenali saat lookup
    admin = _auth_header(client)
    with (
        patch.object(settings, "login_rate_limit_max", 3),
        patch.object(settings, "login_rate_limit_window_sec", 60),
    ):
        for i in range(3):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": f"brute{i}@example.com", "password": "salah"},
            )
            assert resp.status_code == 401

        blocked = client.post(
            "/api/v1/auth/login",
            # Percobaan ke-4 memakai email akun yang ADA agar event
            # ratelimited tercatat pada tenant pemilik akun (lihat router).
            json={"email": "brian@outsourcing.co.id", "password": "salah"},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
    reset_all_limiters()

    logs = client.get(
        "/api/v1/audit/logs",
        headers=admin,
        params={"action_prefix": "auth.login_ratelimited"},
    ).json()
    assert logs["total"] >= 1, f"api={logs}"


def test_rate_limit_endpoint_reset(client):
    settings = get_settings()
    reset_all_limiters()
    with patch.object(settings, "reset_rate_limit_max", 2):
        for _ in range(2):
            r = client.post(
                "/api/v1/auth/reset-password",
                json={"token": "ngasal", "new_password": "password123"},
            )
            assert r.status_code == 422
        blocked = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "ngasal", "new_password": "password123"},
        )
        assert blocked.status_code == 429
    reset_all_limiters()
