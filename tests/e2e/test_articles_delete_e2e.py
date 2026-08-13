"""Real Playwright e2e coverage for SDLCAIP1-14's delete-confirmation flow.

Drives the actual built admin frontend (`vite preview` serving
`frontend/dist`) in a real browser, same pattern as
`test_articles_list_e2e.py`. `window.confirm()` is a real native browser
dialog under Playwright — intercepted via `page.on("dialog", ...)`, not
mocked at the JS layer, so this exercises the actual confirm gate the user
sees.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route

ARTICLES_PATH = "/articles"
TOKEN_STORAGE_KEY = "cms_aipilot_access_token"


def _fulfill_json(route: Route, status: int, body: dict) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def _seed_token_and_open_articles(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}{ARTICLES_PATH}")
    page.evaluate(
        "([key, value]) => localStorage.setItem(key, value)",
        [TOKEN_STORAGE_KEY, "e2e-fake-jwt-token"],
    )
    page.goto(f"{base_url}{ARTICLES_PATH}")


def _route_articles_list(page: Page, items: list[dict]) -> None:
    def handle_list(route: Route) -> None:
        _fulfill_json(
            route,
            200,
            {
                "items": items,
                "total": len(items),
                "total_pages": 1,
                "page": 1,
                "page_size": 10,
            },
        )

    def route_only_api_fetch(route: Route) -> None:
        if route.request.method != "GET":
            route.continue_()
            return
        if route.request.resource_type not in ("fetch", "xhr"):
            route.continue_()
            return
        handle_list(route)

    page.route("**/articles*", route_only_api_fetch)


class TestArticlesDeleteConfirmE2E:
    """AC1: 確認刪除且 API 回 204 時,文章從列表就地移除。"""

    def test_confirm_delete_removes_article(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        items = [{"id": "42", "title": "文章 42", "published_at": "2026-01-01T00:00:00"}]
        _route_articles_list(page, items)

        def handle_delete(route: Route) -> None:
            if route.request.method == "DELETE":
                route.fulfill(status=204, body="")
                return
            route.continue_()

        page.route("**/articles/42", handle_delete)

        page.on("dialog", lambda dialog: dialog.accept())

        _seed_token_and_open_articles(page, frontend_preview_server)

        page.get_by_text("文章 42").wait_for()
        page.get_by_test_id("delete-article-42").click()

        page.get_by_text("尚無文章").wait_for()
        assert page.get_by_text("文章 42").count() == 0


class TestArticlesDeleteCancelE2E:
    """AC2: 取消確認不會刪除文章 -> 不呼叫 API,文章仍在列表。"""

    def test_cancel_delete_keeps_article_and_skips_api(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        items = [{"id": "42", "title": "文章 42", "published_at": "2026-01-01T00:00:00"}]
        _route_articles_list(page, items)

        delete_calls: list[str] = []

        def handle_delete(route: Route) -> None:
            if route.request.method == "DELETE":
                delete_calls.append(route.request.url)
                route.fulfill(status=204, body="")
                return
            route.continue_()

        page.route("**/articles/42", handle_delete)

        page.on("dialog", lambda dialog: dialog.dismiss())

        _seed_token_and_open_articles(page, frontend_preview_server)

        page.get_by_text("文章 42").wait_for()
        page.get_by_test_id("delete-article-42").click()

        # Give any (incorrect) async delete call a chance to fire before
        # asserting it never did.
        page.wait_for_timeout(300)
        assert delete_calls == []
        assert page.get_by_text("文章 42").is_visible()
