"""Tests for SDLCAIP1-23's static homepage article list page generation,
triggered by `create_article`.

Exercises both the unit-level helpers (`_list_page_key`,
`_render_list_page_html`, `_generate_and_upload_list_pages`) directly, and
the `POST /articles` endpoint end-to-end with S3/DynamoDB mocked, following
the same pattern as tests/test_articles.py and tests/test_article_detail_page.py.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import (
    LIST_PAGE_SIZE,
    _generate_and_upload_list_pages,
    _list_page_key,
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


def make_article(index: int) -> dict:
    return {
        "id": f"article-{index}",
        "title": f"Title {index}",
        "content": f"Content {index}",
        "published_at": f"2026-08-{index + 1:02d}T09:00:00",
    }


class TestListPageKey:
    def test_page_1_is_index_html(self):
        assert _list_page_key(1) == "index.html"

    def test_page_2_is_page_2_html(self):
        assert _list_page_key(2) == "page/2.html"

    def test_page_5_is_page_5_html(self):
        assert _list_page_key(5) == "page/5.html"


class TestRenderListPageHtml:
    def test_renders_items_with_escaped_title_and_absolute_links(self):
        items = [
            {
                "id": "a1",
                "title": "<b>Hi</b>",
                "content": "ignored",
                "published_at": "2026-08-10T09:00:00",
            }
        ]
        body = _render_list_page_html(items, page=1, total_pages=1)
        assert "<script>" not in body
        assert "&lt;b&gt;Hi&lt;/b&gt;" in body
        assert 'href="/articles/a1.html"' in body
        assert "2026-08-10 09:00" in body
        assert '<time class="article-list__meta" datetime="2026-08-10T09:00:00">' in body

    def test_pagination_nav_no_prev_on_first_page(self):
        body = _render_list_page_html([], page=1, total_pages=2)
        assert "上一頁" not in body
        assert "下一頁" in body
        assert 'href="/page/2.html"' in body
        assert "第 1 / 2 頁" in body

    def test_pagination_nav_no_next_on_last_page(self):
        body = _render_list_page_html([], page=2, total_pages=2)
        assert "下一頁" not in body
        assert "上一頁" in body
        assert 'href="/index.html"' in body

    def test_pagination_nav_both_on_middle_page(self):
        body = _render_list_page_html([], page=2, total_pages=3)
        assert "上一頁" in body
        assert "下一頁" in body
        assert 'href="/index.html"' in body
        assert 'href="/page/3.html"' in body


class TestGenerateAndUploadListPages:
    """Unit tests for the scan/sort/paginate/upload orchestration."""

    def test_single_page_uploads_index_html_only(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        articles = [make_article(i) for i in range(3)]
        fake_table.scan.return_value = {"Items": articles}

        _generate_and_upload_list_pages(fake_table)

        fake_table.scan.assert_called_once_with(ConsistentRead=True)
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "index.html"
        assert call_kwargs["ContentType"] == "text/html"

    def test_multi_page_uploads_index_and_page_n(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        articles = [make_article(i) for i in range(15)]
        fake_table.scan.return_value = {"Items": articles}

        _generate_and_upload_list_pages(fake_table)

        assert mock_s3.put_object.call_count == 2
        keys = {c.kwargs["Key"] for c in mock_s3.put_object.call_args_list}
        assert keys == {"index.html", "page/2.html"}

        index_call = next(
            c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"] == "index.html"
        )
        assert "article-14" in index_call.kwargs["Body"]
        assert "第 1 / 2 頁" in index_call.kwargs["Body"]

        page2_call = next(
            c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"] == "page/2.html"
        )
        assert "article-0" in page2_call.kwargs["Body"]
        assert "第 2 / 2 頁" in page2_call.kwargs["Body"]

    def test_no_articles_uploads_empty_state_index_html(self, mock_s3, monkeypatch):
        """SDLCAIP1-24 AC3: when the table has no articles left (e.g. after
        deleting the last one), total_pages is floored at 1 so page 1
        (index.html) is still regenerated as an empty-state page, instead of
        leaving S3's index.html stuck with stale pre-deletion content."""
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        fake_table.scan.return_value = {"Items": []}

        _generate_and_upload_list_pages(fake_table)

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "index.html"
        assert '<ul class="article-list"></ul>' in call_kwargs["Body"]
        assert "第 1 / 1 頁" in call_kwargs["Body"]

    def test_page_size_is_ten(self):
        assert LIST_PAGE_SIZE == 10

    def test_upload_failure_raises_and_stops_further_pages(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        articles = [make_article(i) for i in range(15)]
        fake_table.scan.return_value = {"Items": articles}
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )

        from cms_aipilot.main import StaticPageGenerationError

        with pytest.raises(StaticPageGenerationError) as exc_info:
            _generate_and_upload_list_pages(fake_table)
        assert exc_info.value.article_id == "list-page-1"
        assert mock_s3.put_object.call_count == 1


class TestCreateArticleTriggersListPageGeneration:
    """AC1/AC2/AC3: create_article -> list pages regenerated with new article
    sorted newest-first; multi-page case regenerates all pages; first article
    flips homepage from empty to populated."""

    def test_first_article_generates_index_html(self, mock_table, mock_s3):
        mock_table.scan.return_value = {"Items": [
            {
                "id": "new-id",
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": VALID_PAYLOAD["published_at"],
            }
        ]}
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "index.html" in keys
        index_call = next(
            c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"] == "index.html"
        )
        assert VALID_PAYLOAD["title"] in index_call.kwargs["Body"]

    def test_scan_uses_consistent_read(self, mock_table, mock_s3):
        """SDLCAIP1-26: create_article now also scans for the search index,
        so scan() is called once per S3-driven consumer (list pages, search
        index) — every call must still use ConsistentRead=True."""
        mock_table.scan.return_value = {"Items": []}
        client.post("/articles", json=VALID_PAYLOAD)
        assert mock_table.scan.call_count >= 1
        for call in mock_table.scan.call_args_list:
            assert call == ((), {"ConsistentRead": True})

    def test_new_article_sorted_first_among_existing(self, mock_table, mock_s3):
        created_id_holder = {}

        def fake_put_item(Item):
            created_id_holder["id"] = Item["id"]

        mock_table.put_item.side_effect = fake_put_item

        def fake_scan(**kwargs):
            existing = make_article(0)  # published_at 2026-08-02
            new_item = {
                "id": created_id_holder["id"],
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": VALID_PAYLOAD["published_at"],  # 2026-08-10
            }
            return {"Items": [existing, new_item]}

        mock_table.scan.side_effect = fake_scan

        response = client.post("/articles", json=VALID_PAYLOAD)
        article_id = response.json()["id"]

        index_call = next(
            c for c in mock_s3.put_object.call_args_list if c.kwargs["Key"] == "index.html"
        )
        body = index_call.kwargs["Body"]
        assert body.index(f"/articles/{article_id}.html") < body.index("/articles/article-0.html")

    def test_more_than_one_page_regenerates_all_pages(self, mock_table, mock_s3):
        created_id_holder = {}

        def fake_put_item(Item):
            created_id_holder["id"] = Item["id"]

        mock_table.put_item.side_effect = fake_put_item

        def fake_scan(**kwargs):
            existing = [make_article(i) for i in range(10)]
            new_item = {
                "id": created_id_holder["id"],
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": "2026-09-01T00:00:00",
            }
            return {"Items": existing + [new_item]}

        mock_table.scan.side_effect = fake_scan

        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = {c.kwargs["Key"] for c in mock_s3.put_object.call_args_list}
        # article detail page + index.html + page/2.html + search index (SDLCAIP1-26)
        assert keys == {
            f"articles/{response.json()['id']}.html",
            "index.html",
            "page/2.html",
            "search/index.json",
        }


class TestCreateArticleListPageUploadFails:
    """AC4: 靜態列表頁上傳失敗 -> 502 STATIC_PAGE_GENERATION_FAILED, DynamoDB rollback."""

    def test_returns_502_and_rolls_back_when_list_page_upload_fails(self, mock_table, mock_s3):
        mock_table.scan.return_value = {"Items": [
            {
                "id": "new-id",
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": VALID_PAYLOAD["published_at"],
            }
        ]}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "index.html":
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

    def test_rollback_delete_also_fails_logs_error_and_still_returns_502(
        self, mock_table, mock_s3, caplog
    ):
        mock_table.scan.return_value = {"Items": [
            {
                "id": "new-id",
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": VALID_PAYLOAD["published_at"],
            }
        ]}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "index.html":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect
        mock_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "delete-boom"}}, "DeleteItem"
        )

        with caplog.at_level(logging.ERROR, logger="cms_aipilot.main"):
            response = client.post("/articles", json=VALID_PAYLOAD)

        assert response.status_code == 502
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "boom" in error_records[0].getMessage()
        assert "delete-boom" in error_records[0].getMessage()

    def test_article_detail_page_upload_failure_still_rolls_back_without_list_pages(
        self, mock_table, mock_s3
    ):
        """Sanity check: article-detail-page failure (existing SDLCAIP1-8 path)
        still short-circuits before list pages are attempted."""
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 502
        mock_table.scan.assert_not_called()
