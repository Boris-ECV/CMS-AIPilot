"""Real Playwright e2e coverage for SDLCAIP1-33's ArticleForm design-system
styling.

`ArticleForm.test.tsx` (vitest/jsdom) already covers the form's *behavior*
(SDLCAIP1-13) but jsdom does not run a real CSS cascade/layout engine, so it
cannot verify computed colors, fonts, border-radius, text-align or
`:focus-visible` outlines. This suite drives the actual built bundle
(`vite preview` serving `frontend/dist`, same fixture as
`test_design_tokens_e2e.py` / `test_article_form_e2e.py`) in a real browser
to verify the 6 Gherkin ACs of `docs/design/SDLCAIP1-33.md`.
"""

from __future__ import annotations

from playwright.sync_api import Page

ARTICLE_NEW_PATH = "/articles/new"
TOKEN_STORAGE_KEY = "cms_aipilot_access_token"


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


class TestArticleFormColorsAndFontsFromTokensE2E:
    """AC1: 標題/欄位/按鈕的計算後樣式皆來自 design-tokens.css 變數。"""

    def test_title_uses_design_token_color_and_font(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        title = page.get_by_role("heading", name="新增文章")
        title.wait_for()

        color = title.evaluate("el => getComputedStyle(el).color")
        font_size = title.evaluate("el => getComputedStyle(el).fontSize")
        font_weight = title.evaluate("el => getComputedStyle(el).fontWeight")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert color == "rgb(17, 17, 17)"
        # --font-size-h1: 2rem -> 32px
        assert font_size == "32px"
        # --font-weight-h1: 600
        assert font_weight == "600"

    def test_buttons_use_design_token_variant_colors_and_no_border_radius(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        save_button = page.get_by_role("button", name="儲存")
        cancel_button = page.get_by_role("button", name="取消")
        save_button.wait_for()

        save_bg = save_button.evaluate("el => getComputedStyle(el).backgroundColor")
        save_color = save_button.evaluate("el => getComputedStyle(el).color")
        save_radius = save_button.evaluate("el => getComputedStyle(el).borderRadius")

        cancel_bg = cancel_button.evaluate("el => getComputedStyle(el).backgroundColor")
        cancel_color = cancel_button.evaluate("el => getComputedStyle(el).color")
        cancel_border_color = cancel_button.evaluate(
            "el => getComputedStyle(el).borderColor"
        )
        cancel_radius = cancel_button.evaluate("el => getComputedStyle(el).borderRadius")

        # AC4: 儲存 = primary (黑底白字)
        assert save_bg == "rgb(17, 17, 17)"
        assert save_color == "rgb(255, 255, 255)"
        assert save_radius == "0px"

        # AC4: 取消 = secondary (白底黑框)
        assert cancel_bg == "rgb(255, 255, 255)"
        assert cancel_color == "rgb(17, 17, 17)"
        assert cancel_border_color == "rgb(17, 17, 17)"
        assert cancel_radius == "0px"


class TestArticleFormFieldRulesE2E:
    """AC2: label 置於欄位上方靠左；必填以文字標示；錯誤訊息紅色文字 + 圖示。"""

    def test_required_markers_are_visible_text_not_color_only(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        markers = page.locator(".article-form__required-marker")
        markers.first.wait_for()
        assert markers.count() == 3
        for i in range(markers.count()):
            marker = markers.nth(i)
            assert marker.is_visible()
            assert "必填" in (marker.text_content() or "")

    def test_error_message_is_red_and_has_icon(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        # Fill content/date but leave title empty to trigger the JS
        # validation error path (no HTML `required` on title).
        page.get_by_label("內容").fill("我的內容")
        page.get_by_label("發布時間").fill("2026-08-13T10:00")
        page.get_by_role("button", name="儲存").click()

        alert = page.get_by_role("alert")
        alert.wait_for()
        assert "請輸入標題" in (alert.text_content() or "")

        color = alert.evaluate("el => getComputedStyle(el).color")
        # --color-error: #B00020 -> rgb(176, 0, 32)
        assert color == "rgb(176, 0, 32)"

        icon = alert.locator("svg.article-form__error-icon")
        assert icon.count() == 1
        assert icon.is_visible()


class TestArticleFormAccessibilityE2E:
    """AC3 (§8): 欄位有 label，鍵盤導覽時有可見的 focus 樣式。"""

    def test_labels_are_associated_with_fields(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        page.get_by_label("標題").wait_for()
        assert page.get_by_label("標題").count() == 1
        assert page.get_by_label("內容").count() == 1
        assert page.get_by_label("發布時間").count() == 1

    def test_keyboard_focus_shows_visible_outline(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        title_input = page.get_by_label("標題")
        title_input.wait_for()
        # Keyboard-focus (not a mouse click) so :focus-visible actually
        # engages in browsers that distinguish the two.
        page.keyboard.press("Tab")
        title_input.focus()

        outline_style = title_input.evaluate("el => getComputedStyle(el).outlineStyle")
        outline_color = title_input.evaluate("el => getComputedStyle(el).outlineColor")
        outline_width = title_input.evaluate("el => getComputedStyle(el).outlineWidth")

        assert outline_style == "solid"
        assert outline_color == "rgb(17, 17, 17)"
        assert outline_width == "2px"


class TestArticleFormAlignmentE2E:
    """AC5 (§6): 表單 <h1> 置中；label／欄位／按鈕列維持靠左。"""

    def test_title_is_centered_and_fields_and_actions_are_left_aligned(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_token(page, frontend_preview_server, ARTICLE_NEW_PATH)

        title = page.get_by_role("heading", name="新增文章")
        title.wait_for()
        assert title.evaluate("el => getComputedStyle(el).textAlign") == "center"

        field = page.locator(".article-form__field").first
        assert field.evaluate("el => getComputedStyle(el).textAlign") == "left"

        actions = page.locator(".article-form__actions")
        assert actions.evaluate("el => getComputedStyle(el).textAlign") == "left"
