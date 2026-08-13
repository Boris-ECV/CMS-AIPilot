"""Real Playwright e2e coverage for SDLCAIP1-13's article create/edit form.

Drives the actual built admin frontend (`vite preview` serving
`frontend/dist`) in a real browser. See `conftest.py` module docstring for
why API calls are intercepted rather than hitting a live backend server.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route

ARTICLE_NEW_PATH = "/articles/new"
ARTICLES_PATH = "/articles"
TOKEN_STORAGE_KEY = "cms_aipilot_access_token"


def _fulfill_json(route: Route, status: int, body: dict) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def _seed_token(page: Page, base_url: str, path: str) -> None:
    # Seed a valid token before the app boots so RequireAuth lets us through
    # to the form page itself (a real login round-trip is already covered by
    # test_login_flow_e2e.py).
    page.goto(f"{base_url}{path}")
    page.evaluate(
        "([key, value]) => localStorage.setItem(key, value)",
        [TOKEN_STORAGE_KEY, "e2e-fake-jwt-token"],
    )
    page.goto(f"{base_url}{path}")


class TestArticleCreateHappyPathE2E:
    """AC4: 新增模式下填寫有效資料送出 -> 呼叫 POST /articles,成功後導向文章列表頁。"""

    def test_valid_submission_navigates_to_articles_list(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        create_requests: list[dict] = []

        def handle_articles(route: Route) -> None:
            if route.request.method == "POST":
                create_requests.append(json.loads(route.request.post_data or "{}"))
                _fulfill_json(
                    route,
                    201,
                    {
                        "id": "99",
                        "title": "我的標題",
                        "content": "我的內容",
                        "published_at": "2026-08-13T10:00:00",
                    },
                )
                return
            # GET /articles?... after navigating back to the list page.
            _fulfill_json(
                route,
                200,
                {"items": [], "total": 0, "total_pages": 0, "page": 1, "page_size": 10},
            )

        page.route("**/articles*", handle_articles)

        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        page.get_by_label("標題").fill("我的標題")
        page.get_by_label("內容").fill("我的內容")
        page.get_by_label("發布時間").fill("2026-08-13T10:00")
        page.get_by_role("button", name="儲存").click()

        page.wait_for_url(f"**{ARTICLES_PATH}")
        assert page.url.endswith(ARTICLES_PATH)

        assert len(create_requests) == 1
        assert create_requests[0] == {
            "title": "我的標題",
            "content": "我的內容",
            "published_at": "2026-08-13T10:00",
        }


class TestArticleCreateValidationErrorE2E:
    """AC6: 標題留空送出時顯示錯誤訊息,不導向,且不呼叫後端 API。"""

    def test_empty_title_shows_error_and_stays_on_form(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        api_calls: list[str] = []
        page.on(
            "request",
            lambda request: api_calls.append(request.url)
            if request.method == "POST" and request.resource_type in ("fetch", "xhr")
            else None,
        )

        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        page.get_by_label("內容").fill("我的內容")
        page.get_by_label("發布時間").fill("2026-08-13T10:00")
        page.get_by_role("button", name="儲存").click()

        alert = page.get_by_role("alert")
        alert.wait_for()
        assert "請輸入標題" in alert.text_content()

        assert page.url.endswith(ARTICLE_NEW_PATH)
        assert api_calls == []
