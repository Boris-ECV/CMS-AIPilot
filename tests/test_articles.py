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


@pytest.fixture
def mock_table():
    fake_table = MagicMock()
    with patch("cms_aipilot.main.get_articles_table", return_value=fake_table):
        yield fake_table


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
