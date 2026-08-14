"""Tests for SDLCAIP1-26's search index generation, triggered by
`create_article`.

Exercises both the unit-level helpers (`_build_search_index_entry`,
`_generate_and_upload_search_index`) directly, and the `POST /articles`
endpoint end-to-end with S3/DynamoDB mocked, following the same pattern as
tests/test_articles_list_pages.py.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import (
    SEARCH_INDEX_KEY,
    StaticPageGenerationError,
    _build_search_index_entry,
    _generate_and_upload_search_index,
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


class TestSearchIndexKey:
    def test_key_is_search_index_json(self):
        assert SEARCH_INDEX_KEY == "search/index.json"


class TestBuildSearchIndexEntry:
    def test_extracts_id_title_content_published_at(self):
        item = {
            "id": "a1",
            "title": "Hi",
            "content": "Full text content, not truncated.",
            "published_at": "2026-08-10T09:00:00",
        }
        entry = _build_search_index_entry(item)
        assert entry == {
            "id": "a1",
            "title": "Hi",
            "content": "Full text content, not truncated.",
            "published_at": "2026-08-10T09:00:00",
        }


class TestGenerateAndUploadSearchIndex:
    """Unit tests for the scan/build/upload orchestration."""

    def test_uploads_json_array_of_all_items(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        articles = [make_article(i) for i in range(3)]
        fake_table.scan.return_value = {"Items": articles}

        _generate_and_upload_search_index(fake_table)

        fake_table.scan.assert_called_once_with(ConsistentRead=True)
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "search/index.json"
        assert call_kwargs["ContentType"] == "application/json"
        body = json.loads(call_kwargs["Body"])
        assert len(body) == 3
        ids = {entry["id"] for entry in body}
        assert ids == {"article-0", "article-1", "article-2"}

    def test_empty_table_uploads_empty_array(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        fake_table.scan.return_value = {"Items": []}

        _generate_and_upload_search_index(fake_table)

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Key"] == "search/index.json"
        assert json.loads(call_kwargs["Body"]) == []

    def test_non_ascii_content_not_escaped(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        fake_table.scan.return_value = {
            "Items": [
                {
                    "id": "a1",
                    "title": "中文標題",
                    "content": "中文全文內容",
                    "published_at": "2026-08-10T09:00:00",
                }
            ]
        }

        _generate_and_upload_search_index(fake_table)

        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert "中文標題" in call_kwargs["Body"]
        assert "\\u" not in call_kwargs["Body"]

    def test_upload_failure_raises_static_page_generation_error(self, mock_s3, monkeypatch):
        monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-bucket")
        fake_table = MagicMock()
        fake_table.scan.return_value = {"Items": [make_article(0)]}
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )

        with pytest.raises(StaticPageGenerationError) as exc_info:
            _generate_and_upload_search_index(fake_table)
        assert exc_info.value.article_id == "search-index"


class TestCreateArticleTriggersSearchIndexGeneration:
    """AC1/AC2/AC4: create_article -> search/index.json regenerated with the
    new article; index count matches total article count; first article
    flips search/index.json from non-existent to a single-item array."""

    def test_new_article_in_index(self, mock_table, mock_s3):
        created_id_holder = {}

        def fake_put_item(Item):
            created_id_holder["id"] = Item["id"]

        mock_table.put_item.side_effect = fake_put_item

        def fake_scan(**kwargs):
            return {
                "Items": [
                    {
                        "id": created_id_holder["id"],
                        "title": VALID_PAYLOAD["title"],
                        "content": VALID_PAYLOAD["content"],
                        "published_at": VALID_PAYLOAD["published_at"],
                    }
                ]
            }

        mock_table.scan.side_effect = fake_scan

        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201
        article_id = response.json()["id"]

        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        entries = json.loads(index_call.kwargs["Body"])
        assert len(entries) == 1
        assert entries[0]["id"] == article_id
        assert entries[0]["title"] == VALID_PAYLOAD["title"]
        assert entries[0]["content"] == VALID_PAYLOAD["content"]

    def test_index_reflects_all_articles_in_db(self, mock_table, mock_s3):
        created_id_holder = {}

        def fake_put_item(Item):
            created_id_holder["id"] = Item["id"]

        mock_table.put_item.side_effect = fake_put_item

        def fake_scan(**kwargs):
            existing = [make_article(i) for i in range(4)]
            new_item = {
                "id": created_id_holder["id"],
                "title": VALID_PAYLOAD["title"],
                "content": VALID_PAYLOAD["content"],
                "published_at": VALID_PAYLOAD["published_at"],
            }
            return {"Items": existing + [new_item]}

        mock_table.scan.side_effect = fake_scan

        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        entries = json.loads(index_call.kwargs["Body"])
        assert len(entries) == 5

    def test_first_article_creates_index_with_single_item(self, mock_table, mock_s3):
        mock_table.scan.return_value = {
            "Items": [
                {
                    "id": "new-id",
                    "title": VALID_PAYLOAD["title"],
                    "content": VALID_PAYLOAD["content"],
                    "published_at": VALID_PAYLOAD["published_at"],
                }
            ]
        }
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search/index.json" in keys
        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        entries = json.loads(index_call.kwargs["Body"])
        assert len(entries) == 1


class TestCreateArticleSearchIndexUploadFails:
    """AC3: 搜尋索引上傳失敗 -> 502 STATIC_PAGE_GENERATION_FAILED, DynamoDB rollback."""

    def test_returns_502_and_rolls_back_when_search_index_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.scan.return_value = {
            "Items": [
                {
                    "id": "new-id",
                    "title": VALID_PAYLOAD["title"],
                    "content": VALID_PAYLOAD["content"],
                    "published_at": VALID_PAYLOAD["published_at"],
                }
            ]
        }

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search/index.json":
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

    def test_search_index_generated_after_list_pages(self, mock_table, mock_s3):
        """Ordering sanity check: search index step runs after list pages,
        so a list-page failure short-circuits before the index is attempted."""
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "index.html":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 502
        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search/index.json" not in keys
