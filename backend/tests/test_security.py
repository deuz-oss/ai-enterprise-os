"""Test keamanan lanjutan: ganti/reset password, rate limit login, token reset."""

from unittest.mock import patch

from app.core.config import get_settings
from app.core.ratelimit import reset_all_limiters

from tests.conftest import _auth_header, _login_header


def _reset_limiters(client) -> None:
    db = client.testing_session()
    try:
        reset_all_limiters(db)
    finally:
        db.close()


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
        "/api/v1/auth/change-password",
        headers=headers,
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

    issued = client.post(f"/api/v1/auth/users/{user['id']}/password-reset-token", headers=admin)
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


def test_forgot_password_self_service_generic_dan_anti_enumerasi(client):
    """Endpoint publik baru: user minta reset sendiri via email (tanpa admin).

    - Balasan generik SAMA baik email terdaftar atau tidak (anti-enumerasi).
    - Email tak dikenal: tidak ada token dibuat, tidak ada email dikirim.
    - Email dikenal: token asli dibuat & terkirim (di-mock) -> bisa dipakai
      sungguhan lewat /auth/reset-password, sama seperti jalur admin-issued.
    """
    from unittest.mock import patch

    admin = _auth_header(client)
    user = _register(client, admin, "lupa-sandi@example.com")

    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "tidak-ada@example.com"})
    assert unknown.status_code == 202
    unknown_detail = unknown.json()["detail"]

    with patch("app.modules.notifications.service.send_raw_email") as send_mock:
        known = client.post("/api/v1/auth/forgot-password", json={"email": user["email"]})
        assert known.status_code == 202
        assert known.json()["detail"] == unknown_detail  # balasan sama persis
        assert send_mock.call_count == 1
        to, subject, body = send_mock.call_args[0]
        assert to == user["email"]
        assert "reset-password?token=" in body

    token = body.split("token=", 1)[1].strip()
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "sandi-baru-123"},
    )
    assert reset.status_code == 200, reset.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "lupa-sandi@example.com", "password": "sandi-baru-123"},
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


def test_list_users_tidak_bocor_lintas_tenant(client):
    """GET /auth/users — regresi: `User` tidak pakai `TenantMixin` (tenant_id
    nullable utk platform_admin) jadi tidak ikut auto-scope
    `with_loader_criteria`; endpoint list sebelumnya `select(User)` tanpa
    filter manual → admin tenant mana pun bisa lihat nama/email seluruh user
    tenant lain + akun platform_admin."""
    from tests.conftest import _platform_admin_header as plat

    client.post(
        "/api/v1/platform/tenants",
        headers=plat(client),
        json={
            "name": "T Beta",
            "slug": "beta-sec",
            "admin_email": "admin-beta-sec@example.com",
            "admin_password": "password123",
            "admin_full_name": "B",
        },
    )

    default_admin = _auth_header(client)
    listed = client.get("/api/v1/auth/users", headers=default_admin).json()
    emails = {u["email"] for u in listed}
    assert "admin-beta-sec@example.com" not in emails
    assert "platform@example.com" not in emails
    assert all(u.get("email") for u in listed)


def test_rate_limit_login(client):
    settings = get_settings()
    _reset_limiters(client)
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
    _reset_limiters(client)

    logs = client.get(
        "/api/v1/audit/logs",
        headers=admin,
        params={"action_prefix": "auth.login_ratelimited"},
    ).json()
    assert logs["total"] >= 1, f"api={logs}"


def test_rate_limit_endpoint_reset(client):
    settings = get_settings()
    _reset_limiters(client)
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
    _reset_limiters(client)
