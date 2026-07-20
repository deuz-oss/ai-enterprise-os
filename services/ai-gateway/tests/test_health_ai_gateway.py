from ai_gateway.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_live() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-gateway"}


def test_health_ready() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-gateway"}
