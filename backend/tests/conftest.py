from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
# Settings reads the repo's real .env (env_file=(".env", REPO_ROOT/".env"))
# regardless of APP_ENV -- force AI "not configured" for every test run so a
# developer's real AI_BASE_URL/AI_API_KEY in .env can never make tests place
# live, billed calls to a real provider. Tests that need AI configured
# monkeypatch these on the Settings singleton explicitly (see test_ai_usage.py).
os.environ["AI_BASE_URL"] = ""
os.environ["AI_API_KEY"] = ""

import pytest
from app.core.database import Base, get_db
from app.main import create_app
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import create_user
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine, monkeypatch):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # `record_usage()` (core/ai_usage.py) buka `SessionLocal()` sendiri
    # (ad-hoc, di luar DI FastAPI — lihat alasannya di modul itu) — tanpa
    # ini, ia menulis ke engine global yang skemanya sengaja tidak dibuat
    # saat app_env=test, bukan ke database in-memory per-test ini.
    import app.core.ai_usage as ai_usage_module

    monkeypatch.setattr(ai_usage_module, "SessionLocal", TestingSession)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.testing_session = TestingSession  # type: ignore[attr-defined]
        yield c


def _seed_user_idempotent(db, payload: UserCreate, tenant_id):
    """Buat akun seed; abaikan 409 bila sudah pernah dibuat test lain."""
    from app.modules.auth.service import get_by_email
    from fastapi import HTTPException

    if get_by_email(db, payload.email) is not None:
        return
    try:
        create_user(db, payload, tenant_id=tenant_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise


def _auth_header(client: TestClient) -> dict[str, str]:
    """Seed admin tenant default langsung via DB — /auth/register khusus admin."""
    from app.core.bootstrap import ensure_default_tenant

    db = client.testing_session()
    try:
        default_tenant = ensure_default_tenant(db)
        _seed_user_idempotent(
            db,
            UserCreate(
                email="brian@outsourcing.co.id",
                full_name="Brian",
                password="rahasia-123",
                role="admin",
            ),
            tenant_id=default_tenant.id,
        )
    finally:
        db.close()
    return _login_header(client, "brian@outsourcing.co.id", "rahasia-123")


def _platform_admin_header(client: TestClient) -> dict[str, str]:
    """Seed akun platform_admin (tanpa tenant) untuk test provisioning."""
    from app.modules.auth.models import UserRole

    db = client.testing_session()
    try:
        _seed_user_idempotent(
            db,
            UserCreate(
                email="platform@example.com",
                full_name="Platform Admin",
                password="rahasia-123",
                role=UserRole.platform_admin,
            ),
            tenant_id=None,
        )
    finally:
        db.close()
    return _login_header(client, "platform@example.com", "rahasia-123")


def _login_header(client: TestClient, email: str, password: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
