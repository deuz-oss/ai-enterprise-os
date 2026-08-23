from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")

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
def client(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.testing_session = TestingSession  # type: ignore[attr-defined]
        yield c


def _auth_header(client: TestClient) -> dict[str, str]:
    """Seed admin langsung via DB — endpoint /auth/register khusus admin."""
    db = client.testing_session()
    try:
        create_user(
            db,
            UserCreate(
                email="brian@outsourcing.co.id",
                full_name="Brian",
                password="rahasia-123",
                role="admin",
            ),
        )
    finally:
        db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "brian@outsourcing.co.id", "password": "rahasia-123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
