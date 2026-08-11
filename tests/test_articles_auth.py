"""SDLCAIP1-11: article endpoints require JWT auth.

Covers the 401 short-circuit path for all 5 article endpoints (missing
header, malformed header, invalid/expired token) and confirms GET /health
remains unauthenticated.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app)

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
