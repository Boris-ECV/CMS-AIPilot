import logging
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-token"})

VALID_PAYLOAD = {
    "title": "Hello World",
    "content": "Some article content.",
    "published_at": "2026-08-10T09:00:00",
}


@pytest.fixture(autouse=True)
def mock_auth():
    """SDLCAIP1-11: article endpoints require auth; stub out token decoding
    for these business-logic tests (auth behavior itself is covered in
    tests/test_articles_auth.py)."""
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


class TestCreateArticleSuccess:
    """AC1: 成功建立文章並寫入 DynamoDB"""

    def test_returns_201(self, mock_table):
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

    def test_response_contains_id_and_fields(self, mock_table):
        response = client.post("/articles", json=VALID_PAYLOAD)
        body = response.json()
        assert body.get("id")
        assert body["title"] == VALID_PAYLOAD["title"]
        assert body["content"] == VALID_PAYLOAD["content"]
        assert body["published_at"] == VALID_PAYLOAD["published_at"]

    def test_put_item_called_exactly_once_with_attributes(self, mock_table):
        response = client.post("/articles", json=VALID_PAYLOAD)
        body = response.json()
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args.kwargs["Item"]
        assert item["id"] == body["id"]
        assert item["title"] == VALID_PAYLOAD["title"]
        assert item["content"] == VALID_PAYLOAD["content"]
        assert item["published_at"] == "2026-08-10T09:00:00"


class TestCreateArticleMissingTitle:
    """AC2: 缺少必填欄位 title -> 422, no DynamoDB write"""

    def test_returns_422(self, mock_table):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "title"}
        response = client.post("/articles", json=payload)
        assert response.status_code == 422

    def test_no_dynamodb_write(self, mock_table):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "title"}
        client.post("/articles", json=payload)
        mock_table.put_item.assert_not_called()


class TestCreateArticleInvalidPublishedAt:
    """AC3: published_at 格式不合法 -> 422, no DynamoDB write"""

    def test_returns_422(self, mock_table):
        payload = {**VALID_PAYLOAD, "published_at": "not-a-date"}
        response = client.post("/articles", json=payload)
        assert response.status_code == 422

    def test_no_dynamodb_write(self, mock_table):
        payload = {**VALID_PAYLOAD, "published_at": "not-a-date"}
        client.post("/articles", json=payload)
        mock_table.put_item.assert_not_called()


class TestCreateArticleEmptyContent:
    """AC4: content 為空字串 -> 422, no DynamoDB write"""

    def test_returns_422(self, mock_table):
        payload = {**VALID_PAYLOAD, "content": ""}
        response = client.post("/articles", json=payload)
        assert response.status_code == 422

    def test_no_dynamodb_write(self, mock_table):
        payload = {**VALID_PAYLOAD, "content": ""}
        client.post("/articles", json=payload)
        mock_table.put_item.assert_not_called()


EXISTING_ITEM = {
    "id": "existing-id",
    "title": "Old Title",
    "content": "Old content.",
    "published_at": "2026-01-01T00:00:00",
}

UPDATE_PAYLOAD = {
    "title": "New Title",
    "content": "New content.",
    "published_at": "2026-08-10T09:00:00",
}


class TestUpdateArticleSuccess:
    """AC1: 成功更新既有文章"""

    def test_returns_200(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)
        assert response.status_code == 200

    def test_response_contains_updated_id_and_fields(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)
        body = response.json()
        assert body["id"] == EXISTING_ITEM["id"]
        assert body["title"] == UPDATE_PAYLOAD["title"]
        assert body["content"] == UPDATE_PAYLOAD["content"]
        assert body["published_at"] == UPDATE_PAYLOAD["published_at"]

    def test_put_item_called_exactly_once_with_updated_attributes(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        client.put(f"/articles/{EXISTING_ITEM['id']}", json=UPDATE_PAYLOAD)
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args.kwargs["Item"]
        assert item["id"] == EXISTING_ITEM["id"]
        assert item["title"] == UPDATE_PAYLOAD["title"]
        assert item["content"] == UPDATE_PAYLOAD["content"]
        assert item["published_at"] == "2026-08-10T09:00:00"


class TestUpdateArticleNotFound:
    """AC2: 文章不存在 -> 404, no DynamoDB write"""

    def test_returns_404(self, mock_table):
        mock_table.get_item.return_value = {}
        response = client.put("/articles/does-not-exist", json=UPDATE_PAYLOAD)
        assert response.status_code == 404

    def test_response_has_error_detail(self, mock_table):
        mock_table.get_item.return_value = {}
        response = client.put("/articles/does-not-exist", json=UPDATE_PAYLOAD)
        assert response.json().get("detail")

    def test_no_dynamodb_write(self, mock_table):
        mock_table.get_item.return_value = {}
        client.put("/articles/does-not-exist", json=UPDATE_PAYLOAD)
        mock_table.put_item.assert_not_called()


class TestUpdateArticleEmptyTitle:
    """AC3: title 為空字串 -> 422, article data unchanged"""

    def test_returns_422(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        payload = {**UPDATE_PAYLOAD, "title": ""}
        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json=payload)
        assert response.status_code == 422

    def test_no_dynamodb_write(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        payload = {**UPDATE_PAYLOAD, "title": ""}
        client.put(f"/articles/{EXISTING_ITEM['id']}", json=payload)
        mock_table.put_item.assert_not_called()


class TestUpdateArticleMissingFields:
    """AC4: 缺少必填欄位 -> 422, article data unchanged"""

    def test_returns_422(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        response = client.put(f"/articles/{EXISTING_ITEM['id']}", json={"title": "x"})
        assert response.status_code == 422

    def test_no_dynamodb_write(self, mock_table):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        client.put(f"/articles/{EXISTING_ITEM['id']}", json={"title": "x"})
        mock_table.put_item.assert_not_called()


class TestDeleteArticleSuccess:
    """AC1: 成功刪除既有文章"""

    def test_returns_204(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        assert response.status_code == 204

    def test_delete_item_called_exactly_once_with_id(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        client.delete(f"/articles/{EXISTING_ITEM['id']}")
        mock_table.delete_item.assert_called_once_with(Key={"id": EXISTING_ITEM["id"]})


class TestDeleteArticleNotFound:
    """AC2: 文章不存在 -> 404, error message, no DynamoDB delete"""

    def test_returns_404(self, mock_table):
        mock_table.get_item.return_value = {}
        response = client.delete("/articles/does-not-exist")
        assert response.status_code == 404

    def test_response_has_error_detail(self, mock_table):
        mock_table.get_item.return_value = {}
        response = client.delete("/articles/does-not-exist")
        assert response.json().get("detail")

    def test_no_dynamodb_delete(self, mock_table):
        mock_table.get_item.return_value = {}
        client.delete("/articles/does-not-exist")
        mock_table.delete_item.assert_not_called()

    def test_no_s3_delete(self, mock_table, mock_s3):
        """S3 靜態頁刪除不會被觸發（Scenario 3）"""
        mock_table.get_item.return_value = {}
        client.delete("/articles/does-not-exist")
        mock_s3.delete_object.assert_not_called()


class TestDeleteArticleRepeated:
    """AC3: 對已刪除的 id 再次刪除 -> 404"""

    def test_second_delete_returns_404(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        first_response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        assert first_response.status_code == 204

        mock_table.get_item.return_value = {}
        second_response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        assert second_response.status_code == 404
        assert mock_table.delete_item.call_count == 1


class TestDeleteArticleRemovesStaticPage:
    """SDLCAIP1-9 Scenario 1: 成功刪除文章後移除對應 S3 靜態頁物件"""

    def test_returns_204(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        assert response.status_code == 204
        assert response.content == b""

    def test_s3_delete_object_called_with_correct_bucket_and_key(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        client.delete(f"/articles/{EXISTING_ITEM['id']}")
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-articles-static-bucket",
            Key=f"articles/{EXISTING_ITEM['id']}.html",
        )


class TestDeleteArticleStaticPageDeletionFails:
    """SDLCAIP1-9 Scenario 2: S3 靜態頁刪除失敗時阻斷刪除 API 的成功回應"""

    def test_returns_502(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "DeleteObject"
        )
        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        assert response.status_code == 502

    def test_response_body_contains_error_code_and_article_id(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "DeleteObject"
        )
        response = client.delete(f"/articles/{EXISTING_ITEM['id']}")
        body = response.json()
        assert body["error_code"] == "STATIC_PAGE_DELETION_FAILED"
        assert body["article_id"] == EXISTING_ITEM["id"]

    def test_dynamodb_delete_item_still_called(self, mock_table, mock_s3):
        """SDLCAIP1-7 hard-delete 契約不可逆，本票不嘗試復原"""
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "DeleteObject"
        )
        client.delete(f"/articles/{EXISTING_ITEM['id']}")
        mock_table.delete_item.assert_called_once_with(Key={"id": EXISTING_ITEM["id"]})
        mock_table.put_item.assert_not_called()

    def test_failure_logged_as_error(self, mock_table, mock_s3, caplog):
        mock_table.get_item.return_value = {"Item": EXISTING_ITEM}
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "DeleteObject"
        )
        with caplog.at_level(logging.ERROR, logger="cms_aipilot.main"):
            client.delete(f"/articles/{EXISTING_ITEM['id']}")
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert EXISTING_ITEM["id"] in error_records[0].getMessage()
