"""Tests for SDLCAIP1-27's search index regeneration, triggered by
`update_article` and `delete_article`.

Follows the same fixture pattern as tests/test_search_index.py (SDLCAIP1-26)
and tests/test_articles.py's update/delete list-page regeneration tests
(SDLCAIP1-24).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-token"})

EXISTING_ITEM = {
    "id": "existing-id",
    "title": "Original Title",
    "content": "Original content.",
    "published_at": "2026-08-01T09:00:00",
}

UPDATE_PAYLOAD = {
    "title": "Updated Title",
    "content": "Updated content.",
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


class TestUpdateArticleRegeneratesSearchIndex:
    """AC1: PUT /articles/{id} 成功更新後，索引對應項目 title/content 更新。"""

    def test_search_index_uploaded_with_updated_title_and_content(self, mock_table, mock_s3):
        updated_item = {**EXISTING_ITEM, **UPDATE_PAYLOAD}
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": [updated_item]}

        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)

        assert response.status_code == 200
        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        entries = json.loads(index_call.kwargs["Body"])
        assert len(entries) == 1
        assert entries[0]["id"] == EXISTING_ITEM["id"]
        assert entries[0]["title"] == UPDATE_PAYLOAD["title"]
        assert entries[0]["content"] == UPDATE_PAYLOAD["content"]


class TestUpdateArticleSearchIndexUploadFails:
    """AC4: 更新觸發的索引上傳失敗 -> 502 STATIC_PAGE_GENERATION_FAILED + rollback."""

    def test_returns_502_and_rolls_back_when_search_index_upload_fails(
        self, mock_table, mock_s3
    ):
        updated_item = {**EXISTING_ITEM, **UPDATE_PAYLOAD}
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": [updated_item]}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search/index.json":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)

        assert response.status_code == 502
        assert response.json() == {
            "error": "STATIC_PAGE_GENERATION_FAILED",
            "message": "Article could not be published: static page upload failed.",
        }
        mock_table.delete_item.assert_called_once_with(Key={"id": EXISTING_ITEM["id"]})

    def test_search_index_step_runs_after_list_pages(self, mock_table, mock_s3):
        """Ordering sanity check: a list-page failure short-circuits before
        the search index step is attempted."""
        updated_item = {**EXISTING_ITEM, **UPDATE_PAYLOAD}
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": [updated_item]}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "index.html":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)

        assert response.status_code == 502
        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "search/index.json" not in keys


class TestDeleteArticleRegeneratesSearchIndex:
    """AC2/AC3: 刪除文章後索引不再包含該文章；刪除最後一篇後索引為空陣列。"""

    def test_search_index_no_longer_contains_deleted_article(self, mock_table, mock_s3):
        remaining_item = {
            "id": "remaining-id",
            "title": "Remaining Article",
            "content": "Remaining content.",
            "published_at": "2025-01-01T00:00:00",
        }
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        # After the DynamoDB delete, a fresh scan no longer includes the
        # deleted article.
        mock_table.scan.return_value = {"Items": [remaining_item]}

        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")

        assert response.status_code == 204
        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        entries = json.loads(index_call.kwargs["Body"])
        ids = {entry["id"] for entry in entries}
        assert EXISTING_ITEM["id"] not in ids
        assert remaining_item["id"] in ids

    def test_deleting_last_article_makes_index_empty_array(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": []}

        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")

        assert response.status_code == 204
        index_call = next(
            c
            for c in mock_s3.put_object.call_args_list
            if c.kwargs["Key"] == "search/index.json"
        )
        assert json.loads(index_call.kwargs["Body"]) == []


class TestDeleteArticleSearchIndexUploadFails:
    """AC5: 刪除觸發的索引上傳失敗 -> 502 STATIC_SEARCH_INDEX_REGENERATION_FAILED,
    無 rollback。"""

    def test_returns_502_with_new_error_code_and_no_rollback(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "search/index.json":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")

        assert response.status_code == 502
        body = response.json()
        assert body == {
            "error_code": "STATIC_SEARCH_INDEX_REGENERATION_FAILED",
            "detail": "Article deleted but the search index could not be regenerated.",
            "article_id": EXISTING_ITEM["id"],
        }
        # DynamoDB delete already happened and is not rolled back.
        mock_table.delete_item.assert_called_once_with(Key={"id": EXISTING_ITEM["id"]})

    def test_search_index_step_runs_after_list_pages_and_static_page_deletion(
        self, mock_table, mock_s3
    ):
        """Ordering sanity check: a list-page-regeneration failure short-
        circuits before the search-index step is attempted."""
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_table.scan.return_value = {"Items": []}
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )

        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")

        assert response.status_code == 502
        assert response.json()["error_code"] == "STATIC_LIST_PAGE_REGENERATION_FAILED"
