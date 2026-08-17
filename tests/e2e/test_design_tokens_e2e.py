"""Real Playwright e2e coverage for SDLCAIP1-30's AC3: 後台管理介面實際引用
design-tokens.css.

The Gherkin AC3 wording is explicit that this must be verified "用瀏覽器
開發工具可驗證變數值已套用" — i.e. actual computed style values in a real
browser, not just that the component renders with the expected class names.
`vitest`/`jsdom` (see `frontend/src/pages/LoginPage.test.tsx`) does not run a
real CSS cascade/layout engine, so it cannot verify this; a real browser via
Playwright, driving the actual built bundle (`vite preview` serving
`frontend/dist`, same fixture as `test_login_flow_e2e.py`), is required.
"""

from __future__ import annotations

from playwright.sync_api import Page

LOGIN_PATH = "/login"


class TestDesignTokensAppliedOnLoginPageE2E:
    """AC3: frontend/ 的 npm run build 後，design-tokens.css 被
    LoginPage 實際 import 並生效——變數值反映在瀏覽器計算後樣式上。"""

    def test_login_title_uses_design_token_values(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        title = page.get_by_role("heading", name="登入")
        title.wait_for()

        color = title.evaluate("el => getComputedStyle(el).color")
        font_size = title.evaluate("el => getComputedStyle(el).fontSize")
        font_weight = title.evaluate("el => getComputedStyle(el).fontWeight")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert color == "rgb(17, 17, 17)"
        # --font-size-h1: 2rem (root font-size 16px) -> 32px
        assert font_size == "32px"
        # --font-weight-h1: 600
        assert font_weight == "600"

    def test_login_form_uses_design_token_spacing(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        form = page.locator("form.login-page__form")
        form.wait_for()

        padding = form.evaluate("el => getComputedStyle(el).padding")
        # --space-4: 16px
        assert padding == "16px"

    def test_login_submit_button_uses_design_token_spacing(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        page.goto(f"{frontend_preview_server}{LOGIN_PATH}")

        button = page.get_by_role("button", name="登入")
        button.wait_for()

        padding = button.evaluate("el => getComputedStyle(el).padding")
        # padding: var(--space-2) var(--space-4) -> 8px 16px
        assert padding == "8px 16px"
