"""Real Playwright e2e coverage for SDLCAIP1-31's new ACs on the login page.

`tests/e2e/test_design_tokens_e2e.py` (from SDLCAIP1-30) only covers the
minimal integration styling (title color/size/weight, form padding, submit
button padding). SDLCAIP1-31 adds full styling to the same page — the
submit button's full primary-button style (§7), the required-field text
markers (AC3), the error message's red color + icon (AC4), and the visible
focus-visible outline (§8/AC5). None of these are covered by the existing
e2e suite, and jsdom (`LoginPage.test.tsx`) cannot verify computed CSS
values (real cascade/layout), so real-browser Playwright coverage is added
here per docs/02 §3.3.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route

LOGIN_PATH = "/login"


def _fulfill_json(route: Route, status: int, body: dict) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def _route_only_post(route: Route, handler) -> None:
    if route.request.method != "POST":
        route.continue_()
        return
    handler(route)


class TestLoginSubmitButtonPrimaryStyleE2E:
    """AC1: submit 按鈕套用 §7 primary 樣式（黑底白字、無/極小圓角）。"""

    def test_submit_button_uses_black_bg_white_text_and_small_radius(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        button = page.get_by_role("button", name="登入")
        button.wait_for()

        bg_color = button.evaluate("el => getComputedStyle(el).backgroundColor")
        color = button.evaluate("el => getComputedStyle(el).color")
        border_radius = button.evaluate("el => getComputedStyle(el).borderRadius")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert bg_color == "rgb(17, 17, 17)"
        # --color-bg: #FFFFFF -> rgb(255, 255, 255)
        assert color == "rgb(255, 255, 255)"
        assert border_radius == "2px"


class TestLoginRequiredFieldMarkersE2E:
    """AC3: 必填欄位（帳號、密碼）以可見文字標示必填（非僅用顏色）。"""

    def test_username_and_password_have_visible_required_text(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        username_required = page.locator("#username-required")
        password_required = page.locator("#password-required")
        username_required.wait_for()

        assert username_required.text_content().strip() == "必填"
        assert password_required.text_content().strip() == "必填"
        assert username_required.is_visible()
        assert password_required.is_visible()

        username_input = page.locator("#username")
        password_input = page.locator("#password")
        assert username_input.get_attribute("aria-describedby") == "username-required"
        assert password_input.get_attribute("aria-describedby") == "password-required"


class TestLoginErrorMessageStyleE2E:
    """AC4: 錯誤訊息（role="alert"）樣式為紅字 + 圖示，不只靠邊框變色。"""

    def test_error_message_is_red_and_has_icon(
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

        color = alert.evaluate("el => getComputedStyle(el).color")
        # --color-error: #B00020 -> rgb(176, 0, 32)
        assert color == "rgb(176, 0, 32)"

        icon_content = alert.evaluate(
            "el => getComputedStyle(el, '::before').content"
        )
        assert "⚠" in icon_content


class TestLoginFocusVisibleOutlineE2E:
    """AC5: §8 無障礙——鍵盤 focus 樣式可見（非 outline: none 且無替代樣式）。"""

    def test_username_input_shows_visible_focus_outline_on_keyboard_nav(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        page.get_by_label("帳號").focus()

        input_el = page.locator("#username")
        outline_style = input_el.evaluate("el => getComputedStyle(el).outlineStyle")
        outline_width = input_el.evaluate("el => getComputedStyle(el).outlineWidth")

        assert outline_style == "solid"
        assert outline_width == "2px"
