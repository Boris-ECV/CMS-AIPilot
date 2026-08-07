from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app)


def test_health_returns_200_and_status_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_requires_no_auth():
    response = client.get("/health", headers={})
    assert response.status_code == 200
