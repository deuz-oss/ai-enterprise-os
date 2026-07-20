from fastapi.testclient import TestClient
from knowledge_service.main import app

client = TestClient(app)


def test_health_live() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knowledge-service"}


def test_health_ready() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knowledge-service"}
