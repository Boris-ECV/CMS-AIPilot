"""Real Playwright e2e coverage for SDLCAIP1-39's "新增文章" entry point.

Drives the actual built admin frontend (`vite preview` serving
`frontend/dist`) in a real browser. See `conftest.py` module docstring for
why API calls are intercepted rather than hitting a live backend server.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route

ARTICLES_PATH = "/articles"
ARTICLE_NEW_PATH = "/articles/new"
TOKEN_STORAGE_KEY = "cms_aipilot_access_token"


def _fulfill_json(route: Route, status: int, body: dict) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def _seed_token(page: Page, base_url: str, path: str) -> None:
    # Seed a valid token before the app boots so RequireAuth lets us through
    # to the list page itself (a real login round-trip is already covered by
    # test_login_flow_e2e.py).
    page.goto(f"{base_url}{path}")
    page.evaluate(
        "([key, value]) => localStorage.setItem(key, value)",
        [TOKEN_STORAGE_KEY, "e2e-fake-jwt-token"],
    )
    page.goto(f"{base_url}{path}")


def _route_articles_list(page: Page, items: list[dict]) -> None:
    def handle_articles(route: Route) -> None:
        # `page.route("**/articles*", ...)` also matches the browser's own
        # document navigation requests (the SPA shell for /articles and
        # /articles/new), not just the list page's `fetch("/articles?...")`
        # call. Only intercept the actual data fetch; let navigation through
        # untouched so the real app shell still loads.
        if route.request.resource_type not in ("fetch", "xhr"):
            route.continue_()
            return
        _fulfill_json(
            route,
            200,
            {
                "items": items,
                "total": len(items),
                "total_pages": 1 if items else 0,
                "page": 1,
                "page_size": 10,
            },
        )

    page.route("**/articles*", handle_articles)


class TestArticlesListNewEntryPointE2E:
    """AC1+AC2: 列表頁顯示「新增文章」入口,點擊後導向 /articles/new 的空白表單。"""

    def test_new_article_entry_navigates_to_blank_form(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        items = [
            {"id": "1", "title": "第一篇文章", "published_at": "2026-02-01T00:00:00"},
        ]
        _route_articles_list(page, items)

        _seed_token(page, frontend_preview_server, ARTICLES_PATH)

        page.get_by_text("第一篇文章").wait_for()

        new_article_link = page.get_by_role("link", name="新增文章")
        assert new_article_link.is_visible()
        new_article_link.click()

        page.wait_for_url(f"**{ARTICLE_NEW_PATH}")
        assert page.url.endswith(ARTICLE_NEW_PATH)

        # Blank create form: 標題/內容 empty, no pre-filled data.
        assert page.get_by_label("標題").input_value() == ""
        assert page.get_by_label("內容").input_value() == ""


class TestArticlesListNewEntryEmptyStateE2E:
    """AC3: 空列表狀態下「新增文章」入口依然可見可點擊,不因空列表而消失。"""

    def test_new_article_entry_visible_when_list_empty(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _route_articles_list(page, [])

        _seed_token(page, frontend_preview_server, ARTICLES_PATH)

        page.get_by_text("尚無文章").wait_for()

        new_article_link = page.get_by_role("link", name="新增文章")
        assert new_article_link.is_visible()
        assert new_article_link.get_attribute("href") == ARTICLE_NEW_PATH
