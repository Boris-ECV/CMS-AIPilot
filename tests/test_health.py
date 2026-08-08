from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app)


class TestHealthReturns200AndOkStatus:
    """AC1: 呼叫 /health 取得 200 與正常狀態"""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json_content_type(self):
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_body_contains_status_ok(self):
        response = client.get("/health")
        body = response.json()
        assert "status" in body
        assert body["status"] == "ok"

    def test_health_body_shape_only_status_field(self):
        # Spec explicitly excludes extra fields like version/timestamp.
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


class TestHealthRequiresNoAuth:
    """AC2: /health 端點不需要身分驗證"""

    def test_health_without_authorization_header_returns_200(self):
        response = client.get("/health", headers={})
        assert response.status_code == 200
        assert "authorization" not in response.request.headers

    def test_health_with_no_credentials_is_not_unauthorized_or_forbidden(self):
        response = client.get("/health")
        assert response.status_code not in (401, 403)

    def test_health_with_bogus_authorization_header_still_returns_200(self):
        # Even garbage auth data must not be rejected, since no auth is enforced.
        response = client.get("/health", headers={"Authorization": "Bearer not-a-real-token"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
