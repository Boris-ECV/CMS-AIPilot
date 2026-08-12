"""Real Playwright e2e coverage for SDLCAIP1-18's login flow.

Drives the actual built admin frontend (`vite preview` serving
`frontend/dist`) in a real browser. See `conftest.py` module docstring for
why the `/login` network call is intercepted rather than hitting a live
backend server.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route

LOGIN_PATH = "/login"
ARTICLES_PATH = "/articles"


def _fulfill_json(route: Route, status: int, body: dict) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def _route_only_post(route: Route, handler) -> None:
    """`page.route("**/login", ...)` also matches the browser's own document
    navigation request for the `/login` page (GET), not just the login
    form's `fetch("/login", { method: "POST" })` call. Only intercept the
    POST request; let any other method (the page navigation) through
    untouched so the real app shell still loads."""
    if route.request.method != "POST":
        route.continue_()
        return
    handler(route)


class TestLoginSuccessE2E:
    """AC1: 登入成功 -> 呼叫 POST /login、儲存 token、導向文章列表頁路由。"""

    def test_valid_credentials_navigates_to_articles_and_stores_token(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        login_requests: list[dict] = []

        def handle_login(route: Route) -> None:
            login_requests.append(json.loads(route.request.post_data or "{}"))
            _fulfill_json(
                route,
                200,
                {"access_token": "e2e-fake-jwt-token", "token_type": "bearer"},
            )

        page.route(f"**{LOGIN_PATH}", lambda route: _route_only_post(route, handle_login))

        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")
        page.get_by_label("帳號").fill("admin")
        page.get_by_label("密碼").fill("correct-password")
        page.get_by_role("button", name="登入").click()

        page.wait_for_url(f"**{ARTICLES_PATH}")
        assert page.url.endswith(ARTICLES_PATH)

        stored_token = page.evaluate("() => localStorage.getItem('cms_aipilot_access_token')")
        assert stored_token == "e2e-fake-jwt-token"

        assert len(login_requests) == 1
        assert login_requests[0] == {"username": "admin", "password": "correct-password"}


class TestLoginWrongCredentialsE2E:
    """AC2: 帳密錯誤(401)-> 顯示錯誤訊息、不儲存 token、停留在登入頁。"""

    def test_401_shows_error_and_stays_on_login_page(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        def handle_login(route: Route) -> None:
            _fulfill_json(route, 401, {"detail": "Invalid username or password"})

        page.route(f"**{LOGIN_PATH}", lambda route: _route_only_post(route, handle_login))

        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")
        page.get_by_label("帳號").fill("admin")
        page.get_by_label("密碼").fill("wrong-password")
        page.get_by_role("button", name="登入").click()

        alert = page.get_by_role("alert")
        alert.wait_for()
        assert "帳號或密碼錯誤" in alert.text_content()

        assert page.url.endswith(LOGIN_PATH)
        stored_token = page.evaluate("() => localStorage.getItem('cms_aipilot_access_token')")
        assert stored_token is None


class TestAccountLockedE2E:
    """AC3: 帳戶鎖定(429)-> 顯示鎖定提示訊息。"""

    def test_429_shows_lockout_message(self, page: Page, frontend_preview_server: str) -> None:
        def handle_login(route: Route) -> None:
            _fulfill_json(
                route,
                429,
                {
                    "detail": "Account locked. Try again in 900 seconds.",
                    "retry_after_seconds": 900,
                },
            )

        page.route(f"**{LOGIN_PATH}", lambda route: _route_only_post(route, handle_login))

        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")
        page.get_by_label("帳號").fill("admin")
        page.get_by_label("密碼").fill("correct-password")
        page.get_by_role("button", name="登入").click()

        alert = page.get_by_role("alert")
        alert.wait_for()
        assert "帳戶已被鎖定" in alert.text_content()

        stored_token = page.evaluate("() => localStorage.getItem('cms_aipilot_access_token')")
        assert stored_token is None


class TestProtectedRouteRedirectE2E:
    """AC4: 未登入存取受保護頁面 -> 導向登入頁,不發出該頁面的 API 請求。"""

    def test_no_token_redirects_to_login_without_firing_protected_request(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        # Only count actual data-fetch requests (fetch/xhr) to the protected
        # page's API, not the SPA shell's own document/navigation request
        # for the /articles route (that's just the client-side router
        # loading index.html, not a call to the protected backend API).
        articles_api_requests: list[str] = []
        page.on(
            "request",
            lambda request: articles_api_requests.append(request.url)
            if ARTICLES_PATH in request.url and request.resource_type in ("fetch", "xhr")
            else None,
        )

        page.goto(f"{frontend_preview_server}{ARTICLES_PATH}")
        page.wait_for_url(f"**{LOGIN_PATH}")

        assert page.url.endswith(LOGIN_PATH)
        assert page.get_by_role("heading", name="登入").is_visible()
        assert articles_api_requests == []
