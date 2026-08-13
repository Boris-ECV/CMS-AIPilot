"""Real Playwright e2e coverage for SDLCAIP1-19's articles list page.

Drives the actual built admin frontend (`vite preview` serving
`frontend/dist`) in a real browser. See `conftest.py` module docstring for
why API calls are intercepted rather than hitting a live backend server.
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


class TestArticlesListHappyPathE2E:
    """AC1: 有資料時列表正常呈現 -> 顯示每篇文章的標題與 published_at。"""

    def test_articles_render_title_and_published_at(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        items = [
            {"id": "1", "title": "第一篇文章", "published_at": "2026-02-01T00:00:00"},
            {"id": "2", "title": "第二篇文章", "published_at": "2026-01-01T00:00:00"},
        ]

        def handle_articles(route: Route) -> None:
            _fulfill_json(
                route,
                200,
                {
                    "items": items,
                    "total": 2,
                    "total_pages": 1,
                    "page": 1,
                    "page_size": 10,
                },
            )

        def route_only_api_fetch(route: Route) -> None:
            # `page.route("**/articles*", ...)` also matches the browser's
            # own document navigation request for the `/articles` page (the
            # SPA shell), not just the list page's `fetch("/articles?...")`
            # call. Only intercept the actual data fetch; let the page
            # navigation through untouched so the real app shell still
            # loads.
            if route.request.resource_type not in ("fetch", "xhr"):
                route.continue_()
                return
            handle_articles(route)

        page.route("**/articles*", route_only_api_fetch)

        # Seed a valid token before the app boots so RequireAuth lets us
        # through to the articles page itself (a real login round-trip is
        # already covered by test_login_flow_e2e.py).
        page.goto(f"{frontend_preview_server}{ARTICLES_PATH}")
        page.evaluate(
            "([key, value]) => localStorage.setItem(key, value)",
            [TOKEN_STORAGE_KEY, "e2e-fake-jwt-token"],
        )
        page.goto(f"{frontend_preview_server}{ARTICLES_PATH}")

        page.get_by_text("第一篇文章").wait_for()
        assert page.get_by_text("第二篇文章").is_visible()
        assert page.get_by_text("2026-02-01T00:00:00").is_visible()
        assert page.get_by_text("2026-01-01T00:00:00").is_visible()

        rows = page.get_by_role("row")
        assert rows.count() == 3  # header + 2 data rows
