"""SDLCAIP1-11: article endpoints require JWT auth.

Covers the 401 short-circuit path for all 5 article endpoints (missing
header, malformed header, invalid/expired token) and confirms GET /health
remains unauthenticated.
"""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from cms_aipilot.auth import ALGORITHM
from cms_aipilot.main import app

client = TestClient(app)

JWT_SECRET = "test-secret-value-that-is-at-least-32-bytes-long"
ADMIN_USERNAME = "admin"

VALID_PAYLOAD = {
    "title": "Hello World",
    "content": "Some article content.",
    "published_at": "2026-08-10T09:00:00",
}

ARTICLE_ID = "existing-id"

PROTECTED_REQUESTS = [
    ("post", "/articles", {"json": VALID_PAYLOAD}),
    ("get", "/articles", {}),
    ("get", f"/articles/{ARTICLE_ID}", {}),
    ("put", f"/articles/{ARTICLE_ID}", {"json": VALID_PAYLOAD}),
    ("delete", f"/articles/{ARTICLE_ID}", {}),
]


@pytest.fixture
def mock_table():
    fake_table = MagicMock()
    with patch("cms_aipilot.main.get_articles_table", return_value=fake_table):
        yield fake_table


@pytest.fixture
def mock_ssm(monkeypatch):
    """Real SSM-backed JWT secret so decode_access_token runs unmocked
    end-to-end (create_access_token/jwt.encode -> require_auth -> endpoint)."""
    from cms_aipilot import auth as auth_module

    auth_module.get_jwt_secret.cache_clear()
    monkeypatch.setenv("JWT_SECRET_SSM_PARAM", "/cms-aipilot/auth/jwt-secret")

    fake_ssm_client = MagicMock()
    fake_ssm_client.get_parameter.return_value = {"Parameter": {"Value": JWT_SECRET}}
    with patch("cms_aipilot.auth.boto3.client", return_value=fake_ssm_client):
        yield
    auth_module.get_jwt_secret.cache_clear()


class TestMissingAuthorizationHeader:
    """Missing Authorization header -> 401 on all 5 protected endpoints."""

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_returns_401(self, mock_table, method, path, kwargs):
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_no_dynamodb_access(self, mock_table, method, path, kwargs):
        getattr(client, method)(path, **kwargs)
        mock_table.put_item.assert_not_called()
        mock_table.get_item.assert_not_called()
        mock_table.scan.assert_not_called()
        mock_table.delete_item.assert_not_called()


class TestMalformedAuthorizationHeader:
    """Malformed header (e.g. missing 'Bearer ' prefix) -> 401, no crash."""

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_returns_401_without_bearer_prefix(self, mock_table, method, path, kwargs):
        response = getattr(client, method)(
            path, headers={"Authorization": "some-raw-token"}, **kwargs
        )
        assert response.status_code == 401

    def test_returns_401_with_wrong_scheme(self, mock_table):
        response = client.get("/articles", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert response.status_code == 401

    def test_returns_401_with_empty_bearer_token(self, mock_table):
        response = client.get("/articles", headers={"Authorization": "Bearer "})
        assert response.status_code == 401


class TestInvalidToken:
    """Expired / bad-signature / garbage JWT -> 401, never 500."""

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_returns_401_for_invalid_token(self, mock_table, method, path, kwargs):
        with patch("cms_aipilot.main.decode_access_token", return_value=None):
            response = getattr(client, method)(
                path, headers={"Authorization": "Bearer invalid-or-expired-token"}, **kwargs
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"


class TestValidTokenGrantsAccess:
    """A valid token allows the request through to normal business logic."""

    def test_get_articles_succeeds_with_valid_token(self, mock_table):
        mock_table.scan.return_value = {"Items": []}
        with patch(
            "cms_aipilot.main.decode_access_token", return_value={"sub": "admin"}
        ):
            response = client.get(
                "/articles", headers={"Authorization": "Bearer valid-token"}
            )
        assert response.status_code == 200


class TestHealthEndpointUnaffected:
    """GET /health remains unauthenticated (out of scope for this ticket)."""

    def test_returns_200_without_authorization_header(self):
        response = client.get("/health")
        assert response.status_code == 200


class TestRealInvalidTokenEndToEnd:
    """Same as TestInvalidToken but exercises the *real* decode_access_token
    (genuine expired/bad-signature/malformed JWTs), not a mocked stand-in --
    confirms the require_auth <-> decode_access_token wiring itself, not just
    the branch that fires when decode_access_token happens to return None."""

    def _expired_token(self) -> str:
        now = int(time.time())
        payload = {"sub": ADMIN_USERNAME, "iat": now - 100, "exp": now - 50}
        return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    def _bad_signature_token(self) -> str:
        now = int(time.time())
        payload = {"sub": ADMIN_USERNAME, "iat": now, "exp": now + 3600}
        return jwt.encode(
            payload, "wrong-secret-value-that-is-at-least-32-bytes", algorithm=ALGORITHM
        )

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_expired_token_returns_401(self, mock_table, mock_ssm, method, path, kwargs):
        response = getattr(client, method)(
            path, headers={"Authorization": f"Bearer {self._expired_token()}"}, **kwargs
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_bad_signature_token_returns_401(self, mock_table, mock_ssm, method, path, kwargs):
        response = getattr(client, method)(
            path,
            headers={"Authorization": f"Bearer {self._bad_signature_token()}"},
            **kwargs,
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_garbage_token_returns_401_not_500(self, mock_table, mock_ssm, method, path, kwargs):
        """Malformed-header-validation-failure-does-not-crash-server scenario,
        with a genuinely unparsable JWT string (not merely a missing header)."""
        response = getattr(client, method)(
            path, headers={"Authorization": "Bearer not.a.jwt"}, **kwargs
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path,kwargs", PROTECTED_REQUESTS)
    def test_no_dynamodb_access_on_expired_token(
        self, mock_table, mock_ssm, method, path, kwargs
    ):
        getattr(client, method)(
            path, headers={"Authorization": f"Bearer {self._expired_token()}"}, **kwargs
        )
        mock_table.put_item.assert_not_called()
        mock_table.get_item.assert_not_called()
        mock_table.scan.assert_not_called()
        mock_table.delete_item.assert_not_called()


class TestServerRemainsAvailableAfterAuthFailures:
    """Scenario: token validation failure does not crash the server -- it
    keeps serving subsequent requests, including a genuinely valid one."""

    def test_server_serves_next_request_after_malformed_header(self, mock_table, mock_ssm):
        bad_response = client.get("/articles", headers={"Authorization": "garbage no bearer"})
        assert bad_response.status_code == 401

        from cms_aipilot.auth import create_access_token

        mock_table.scan.return_value = {"Items": []}
        token = create_access_token(subject=ADMIN_USERNAME)
        good_response = client.get(
            "/articles", headers={"Authorization": f"Bearer {token}"}
        )
        assert good_response.status_code == 200


class TestRealValidTokenGrantsAccessPerEndpoint:
    """Genuine end-to-end valid-token pass-through (real create_access_token
    + real decode_access_token, not mocked) for every one of the 5 protected
    endpoints -- not just GET /articles."""

    def _auth_headers(self) -> dict:
        from cms_aipilot.auth import create_access_token

        return {"Authorization": f"Bearer {create_access_token(subject=ADMIN_USERNAME)}"}

    def test_post_articles_returns_201(self, mock_table, mock_ssm, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        with patch("cms_aipilot.main.get_s3_client", return_value=MagicMock()):
            response = client.post(
                "/articles", json=VALID_PAYLOAD, headers=self._auth_headers()
            )
        assert response.status_code == 201

    def test_get_articles_returns_200(self, mock_table, mock_ssm):
        mock_table.scan.return_value = {"Items": []}
        response = client.get("/articles", headers=self._auth_headers())
        assert response.status_code == 200

    def test_get_article_by_id_returns_200(self, mock_table, mock_ssm):
        mock_table.get_item.return_value = {
            "Item": {
                "id": ARTICLE_ID,
                "title": "T",
                "content": "C",
                "published_at": "2026-01-01T00:00:00",
            }
        }
        response = client.get(f"/articles/{ARTICLE_ID}", headers=self._auth_headers())
        assert response.status_code == 200

    def test_put_article_returns_200(self, mock_table, mock_ssm, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        mock_table.get_item.return_value = {
            "Item": {
                "id": ARTICLE_ID,
                "title": "Old",
                "content": "Old content",
                "published_at": "2026-01-01T00:00:00",
            }
        }
        with patch("cms_aipilot.main.get_s3_client", return_value=MagicMock()):
            response = client.put(
                f"/articles/{ARTICLE_ID}", json=VALID_PAYLOAD, headers=self._auth_headers()
            )
        assert response.status_code == 200

    def test_delete_article_returns_204(self, mock_table, mock_ssm, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        mock_table.get_item.return_value = {
            "Item": {
                "id": ARTICLE_ID,
                "title": "T",
                "content": "C",
                "published_at": "2026-01-01T00:00:00",
            }
        }
        with patch("cms_aipilot.main.get_s3_client", return_value=MagicMock()):
            response = client.delete(f"/articles/{ARTICLE_ID}", headers=self._auth_headers())
        assert response.status_code == 204
