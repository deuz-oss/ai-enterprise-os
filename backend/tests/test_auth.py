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
