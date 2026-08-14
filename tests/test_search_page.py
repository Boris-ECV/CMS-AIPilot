"""Tests for SDLCAIP1-28's front-end search page (search.html).

Exercises `_generate_and_upload_search_page` directly (S3 mocked, same
pattern as tests/test_article_detail_page.py and tests/test_search_index.py)
and the create/update/delete endpoints end-to-end to verify the integration
points wire in the new call. Browser-executed behaviour (AC2/3/4/5/6/7/8 —
input-driven filtering, case-insensitive substring match, empty-state,
no-pagination, empty-keyword no-op, no backend API call) is covered by the
Playwright e2e suite in tests/e2e/; this file only asserts that the produced
HTML/JS string faithfully contains the designed logic, and that the backend
orchestration (upload key/content-type, failure handling, rollback,
cross-page links) is correct.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import (
    SEARCH_PAGE_KEY,
    Article,
    StaticPageGenerationError,
    _generate_and_upload_search_page,
    _generate_and_upload_static_page,
    _render_list_page_html,
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


class TestSearchPageKey:
    def test_key_is_search_html_at_bucket_root(self):
        assert SEARCH_PAGE_KEY == "search.html"


class TestGenerateAndUploadSearchPage:
    """Unit tests for the standalone static skeleton page generator."""

    def test_uploads_to_search_html_with_text_html_content_type(self, mock_s3):
        _generate_and_upload_search_page()

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-articles-static-bucket"
        assert call_kwargs["Key"] == "search.html"
        assert call_kwargs["ContentType"] == "text/html"

    def test_upload_failure_raises_static_page_generation_error(self, mock_s3):
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )
        with pytest.raises(StaticPageGenerationError) as exc_info:
            _generate_and_upload_search_page()
        assert exc_info.value.article_id == "search-page"

    def test_body_contains_search_input_and_results_containers(self, mock_s3):
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert '<input type="text" id="search-input"' in body
        assert 'class="search-form__input"' in body
        assert '<ul class="article-list" id="search-results"></ul>' in body
        assert (
            '<p class="search-empty" id="search-empty" hidden>查無符合的文章</p>' in body
        )
        assert '<title>搜尋文章</title>' in body

    def test_body_fetches_search_index_json_not_a_backend_api(self, mock_s3):
        """AC8: the only data source is the pre-downloaded search/index.json,
        fetched client-side — no backend API endpoint is referenced."""
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert 'fetch("/search/index.json")' in body
        assert "/articles" not in body.split("<script>")[0]  # nav/head has no API refs

    def test_body_uses_input_event_not_submit(self, mock_s3):
        """AC2/AC3/AC4: real-time filtering on every keystroke, not on form
        submit."""
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert 'input.addEventListener("input"' in body
        assert 'onsubmit="return false;"' in body

    def test_body_uses_case_insensitive_substring_match_on_title_and_content(self, mock_s3):
        """AC2/AC3/AC4."""
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert "item.title.toLowerCase().indexOf(lowerKeyword) !== -1" in body
        assert "item.content.toLowerCase().indexOf(lowerKeyword) !== -1" in body

    def test_body_shows_empty_message_only_when_zero_matches(self, mock_s3):
        """AC5/AC7."""
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert "if (keyword === \"\") {" in body
        assert "return; // AC7" in body
        assert "if (matches.length === 0) {" in body
        assert "emptyEl.hidden = false; // AC5" in body

    def test_body_renders_all_matches_without_pagination_or_slicing(self, mock_s3):
        """AC6: no pagination — the filter/forEach loop has no length cap or
        slice()."""
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert ".slice(" not in body
        assert "matches.forEach(function (item) {" in body

    def test_body_uses_text_content_not_inner_html_for_title(self, mock_s3):
        _generate_and_upload_search_page()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert "a.textContent = item.title;" in body


class TestSearchPageLinkedFromOtherPages:
    """AC1: search.html reachable from other static pages."""

    def test_article_detail_page_links_to_search_page(self, mock_s3):
        article = Article(
            id="a1",
            title="T",
            content="C",
            published_at="2026-01-01T00:00:00",
        )
        _generate_and_upload_static_page(article)
        body = mock_s3.put_object.call_args.kwargs["Body"]
        assert '<a href="/search.html">搜尋文章</a>' in body

    def test_list_page_links_to_search_page(self):
        body = _render_list_page_html(page_items=[], page=1, total_pages=1)
        assert '<a href="/search.html">搜尋文章</a>' in body

    def test_paginated_list_page_links_to_search_page(self):
        body = _render_list_page_html(page_items=[], page=2, total_pages=3)
        assert '<a href="/search.html">搜尋文章</a>' in body


class TestCreateArticleTriggersSearchPageGeneration:
    def test_search_page_uploaded_after_create(self, mock_table, mock_s3):
        mock_table.scan.return_value = {"Items": []}
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search.html" in keys

    def test_returns_502_and_rolls_back_when_search_page_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search.html":
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


class TestUpdateArticleTriggersSearchPageGeneration:
    def test_search_page_uploaded_after_update(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 200

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search.html" in keys

    def test_returns_502_when_search_page_upload_fails(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search.html":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 502
        mock_table.delete_item.assert_called_once_with(Key={"id": "a1"})


class TestDeleteArticleTriggersSearchPageGeneration:
    def test_search_page_uploaded_after_delete(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.delete("/articles/a1")
        assert response.status_code == 204

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search.html" in keys

    def test_returns_502_with_dedicated_error_code_when_search_page_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search.html":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.delete("/articles/a1")
        assert response.status_code == 502
        assert response.json()["error_code"] == "STATIC_SEARCH_PAGE_REGENERATION_FAILED"
