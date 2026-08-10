from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cms_aipilot.main import app

client = TestClient(app)


@pytest.fixture
def mock_table():
    fake_table = MagicMock()
    with patch("cms_aipilot.main.get_articles_table", return_value=fake_table):
        yield fake_table


def make_article(index: int) -> dict:
    return {
        "id": f"article-{index}",
        "title": f"Title {index}",
        "content": f"Content {index}",
        "published_at": f"2026-08-{index + 1:02d}T09:00:00",
    }


class TestListArticlesPaginated:
    """AC1: 分頁列出文章，含摘要欄位、分頁資訊，依 published_at 由新到舊排序"""

    def test_returns_200_with_page_of_summaries(self, mock_table):
        articles = [make_article(i) for i in range(15)]
        mock_table.scan.return_value = {"Items": articles}

        response = client.get("/articles", params={"page": 1, "page_size": 10})

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 10
        assert body["total"] == 15
        assert body["total_pages"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 10

    def test_items_are_summaries_and_sorted_newest_first(self, mock_table):
        articles = [make_article(i) for i in range(15)]
        mock_table.scan.return_value = {"Items": articles}

        response = client.get("/articles", params={"page": 1, "page_size": 10})
        body = response.json()

        first_item = body["items"][0]
        assert set(first_item.keys()) == {"id", "title", "published_at"}
        assert first_item["id"] == "article-14"

        published_dates = [item["published_at"] for item in body["items"]]
        assert published_dates == sorted(published_dates, reverse=True)


class TestListArticlesEmpty:
    """AC2: 沒有任何文章 -> 200, 空陣列, total 為 0"""

    def test_returns_empty_list(self, mock_table):
        mock_table.scan.return_value = {"Items": []}

        response = client.get("/articles", params={"page": 1, "page_size": 10})

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0


class TestGetArticleById:
    """AC3: 依 id 查詢單篇文章 -> 200, 含完整欄位"""

    def test_returns_full_article(self, mock_table):
        article = make_article(0)
        mock_table.get_item.return_value = {"Item": article}

        response = client.get(f"/articles/{article['id']}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == article["id"]
        assert body["title"] == article["title"]
        assert body["content"] == article["content"]
        assert body["published_at"] == article["published_at"]


class TestGetArticleByIdNotFound:
    """AC4: 查詢不存在的 id -> 404"""

    def test_returns_404(self, mock_table):
        mock_table.get_item.return_value = {}

        response = client.get("/articles/does-not-exist")

        assert response.status_code == 404


class TestListArticlesInvalidPagination:
    """AC5: page=0 (不合法分頁參數) -> 422"""

    def test_returns_422(self, mock_table):
        response = client.get("/articles", params={"page": 0, "page_size": 10})

        assert response.status_code == 422
