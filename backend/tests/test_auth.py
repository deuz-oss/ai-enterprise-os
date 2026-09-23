from tests.conftest import _auth_header


def test_register_login_me(client):
    headers = _auth_header(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "brian@outsourcing.co.id"
    assert body["role"] == "admin"


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "x@y.co.id", "full_name": "X", "password": "rahasia-123"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": "x@y.co.id", "password": "salah"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_tenant_admin_cannot_grant_platform_admin(client):
    """Regresi: admin tenant tidak boleh membuat/menaikkan akun ke platform_admin
    (dulu lolos -> akses penuh /platform/* lintas tenant)."""
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={
            "email": "eskalasi@y.co.id",
            "full_name": "E",
            "password": "rahasia-123",
            "role": "platform_admin",
        },
    )
    assert resp.status_code == 422

    created = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": "biasa@y.co.id", "full_name": "B", "password": "rahasia-123"},
    )
    assert created.status_code == 201
    patched = client.patch(
        f"/api/v1/auth/users/{created.json()['id']}",
        headers=headers,
        json={"role": "platform_admin"},
    )
    assert patched.status_code == 422


def test_tenant_bound_platform_role_rejected_by_guard(client):
    """Defense in depth: akun bertenanta dgn role platform_admin (mis. data
    lama) tetap ditolak di /platform/*."""
    from app.modules.auth.models import User, UserRole

    headers = _auth_header(client)
    db = client.testing_session()
    try:
        user = db.query(User).filter_by(email="brian@outsourcing.co.id").one()
        user.role = UserRole.platform_admin
        db.commit()
    finally:
        db.close()
    assert client.get("/api/v1/platform/tenants", headers=headers).status_code == 403
