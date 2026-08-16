"""Tests for SDLCAIP1-30's shared visual style token stylesheet
(design-tokens.css).

Exercises `_generate_and_upload_design_tokens` directly (S3 mocked, same
pattern as tests/test_search_page.py) and the create/update/delete
endpoints end-to-end to verify the integration points wire in the new
call. This file asserts the backend orchestration (upload key/content-type,
failure handling, rollback) is correct; the exact CSS custom property
values are the responsibility of docs/design-system.md and the static
file itself (docs/design/SDLCAIP1-30.md 介面/API 契約).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import (
    DESIGN_TOKENS_KEY,
    StaticPageGenerationError,
    _generate_and_upload_design_tokens,
    app,
)

client = TestClient(app, headers={"Authorization": "Bearer test-token"})

VALID_PAYLOAD = {
    "title": "Hello World",
    "content": "Some article content.",
    "published_at": "2026-08-10T09:00:00",
}


@pytest.fixture(autouse=True)
def mock_auth():
    with patch(
        "cms_aipilot.main.decode_access_token", return_value={"sub": "admin"}
    ) as mocked:
        yield mocked


@pytest.fixture
def mock_table():
    fake_table = MagicMock()
    with patch("cms_aipilot.main.get_articles_table", return_value=fake_table):
        yield fake_table


@pytest.fixture
def mock_s3(monkeypatch):
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        yield fake_s3


class TestDesignTokensKey:
    def test_key_is_design_tokens_css_at_bucket_root(self):
        assert DESIGN_TOKENS_KEY == "design-tokens.css"


class TestGenerateAndUploadDesignTokens:
    """Unit tests for the standalone stylesheet upload function."""

    def test_uploads_to_design_tokens_css_with_text_css_content_type(self, mock_s3):
        _generate_and_upload_design_tokens()

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-articles-static-bucket"
        assert call_kwargs["Key"] == "design-tokens.css"
        assert call_kwargs["ContentType"] == "text/css"

    def test_body_contains_root_selector_and_known_tokens(self, mock_s3):
        _generate_and_upload_design_tokens()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert ":root {" in body
        assert "--color-bg: #FFFFFF;" in body
        assert "--color-text-primary: #111111;" in body
        assert "--space-4: 16px;" in body
        assert "--breakpoint-tablet-min: 768px;" in body

    def test_upload_failure_raises_static_page_generation_error(self, mock_s3):
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )
        with pytest.raises(StaticPageGenerationError) as exc_info:
            _generate_and_upload_design_tokens()
        assert exc_info.value.article_id == "design-tokens"

    def test_read_failure_raises_static_page_generation_error(self, mock_s3):
        with (
            patch("cms_aipilot.main._DESIGN_TOKENS_PATH", "/nonexistent/path.css"),
            pytest.raises(StaticPageGenerationError) as exc_info,
        ):
            _generate_and_upload_design_tokens()
        assert exc_info.value.article_id == "design-tokens"
        mock_s3.put_object.assert_not_called()


class TestCreateArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_create(self, mock_table, mock_s3):
        mock_table.scan.return_value = {"Items": []}
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_and_rolls_back_when_design_tokens_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.post("/articles", json=VALID_PAYLOAD)

        assert response.status_code == 502
        assert response.json() == {
            "error": "STATIC_PAGE_GENERATION_FAILED",
            "message": "Article could not be published: static page upload failed.",
        }
        article_id = mock_table.put_item.call_args.kwargs["Item"]["id"]
        mock_table.delete_item.assert_called_once_with(Key={"id": article_id})


class TestUpdateArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_update(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 200

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_when_design_tokens_upload_fails(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 502
        mock_table.delete_item.assert_called_once_with(Key={"id": "a1"})


class TestDeleteArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_delete(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.delete("/articles/a1")
        assert response.status_code == 204

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_with_dedicated_error_code_when_design_tokens_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.delete("/articles/a1")
        assert response.status_code == 502
        assert response.json()["error_code"] == "STATIC_DESIGN_TOKENS_REGENERATION_FAILED"
