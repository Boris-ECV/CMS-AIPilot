"""Real Playwright e2e coverage for SDLCAIP1-32's design-system styling on
the articles list page.

`ArticlesList.test.tsx` (jsdom) is behavioral only and cannot verify real
computed CSS (cascade/layout), so per docs/02 §3.3 this adds real-browser
coverage for the visual ACs: token-based colors/fonts (AC1), row separation
via `border-spacing` instead of border/shadow/background (AC2), button
variant styling incl. the danger variant (AC3), and the visible
focus-visible outline (AC4/§8). `test_articles_list_e2e.py` (SDLCAIP1-19)
already covers this page's data/behavior; this file only adds styling
coverage, following the same route-interception + token-seeding pattern.
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


def _seed_articles_route(page: Page) -> None:
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
                "total_pages": 2,
                "page": 1,
                "page_size": 10,
            },
        )

    def route_only_api_fetch(route: Route) -> None:
        if route.request.resource_type not in ("fetch", "xhr"):
            route.continue_()
            return
        handle_articles(route)

    page.route("**/articles*", route_only_api_fetch)


def _goto_authenticated_articles_page(page: Page, base_url: str) -> None:
    # Seed a valid token before the app boots so RequireAuth lets us through
    # to the articles page itself (mirrors test_articles_list_e2e.py).
    page.goto(f"{base_url}{ARTICLES_PATH}")
    page.evaluate(
        "([key, value]) => localStorage.setItem(key, value)",
        [TOKEN_STORAGE_KEY, "e2e-fake-jwt-token"],
    )
    page.goto(f"{base_url}{ARTICLES_PATH}")


class TestArticlesListTableTokenStylingE2E:
    """AC1: 表格套用 design-tokens.css 色彩/字體變數。"""

    def test_table_cell_uses_token_color_and_font(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        cell = page.get_by_text("第一篇文章")
        cell.wait_for()

        color = cell.evaluate("el => getComputedStyle(el).color")
        font_size = cell.evaluate("el => getComputedStyle(el).fontSize")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert color == "rgb(17, 17, 17)"
        # --font-size-body: 1rem -> 16px
        assert font_size == "16px"


class TestArticlesListRowSeparationE2E:
    """AC2: 列分隔用 border-spacing,表格本身無 border/box-shadow/background。"""

    def test_table_uses_border_spacing_not_border_or_shadow(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        table = page.get_by_role("table")
        table.wait_for()

        border_spacing = table.evaluate("el => getComputedStyle(el).borderSpacing")
        border_collapse = table.evaluate("el => getComputedStyle(el).borderCollapse")
        box_shadow = table.evaluate("el => getComputedStyle(el).boxShadow")
        background_color = table.evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )

        # --space-3: 12px, horizontal 0
        assert border_spacing == "0px 12px"
        assert border_collapse == "separate"
        assert box_shadow == "none"
        assert background_color in ("rgba(0, 0, 0, 0)", "transparent")


class TestArticlesListButtonVariantsE2E:
    """AC3: 編輯/刪除/上一頁/下一頁按鈕套用 secondary/danger 樣式,無/極小圓角。"""

    def test_edit_link_uses_secondary_style(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        edit_link = page.get_by_role("link", name="編輯").first
        edit_link.wait_for()

        border = edit_link.evaluate("el => getComputedStyle(el).borderTopColor")
        color = edit_link.evaluate("el => getComputedStyle(el).color")
        border_radius = edit_link.evaluate("el => getComputedStyle(el).borderRadius")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert border == "rgb(17, 17, 17)"
        assert color == "rgb(17, 17, 17)"
        assert border_radius == "0px"

    def test_delete_button_uses_danger_style(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        delete_button = page.get_by_test_id("delete-article-1")
        delete_button.wait_for()

        border = delete_button.evaluate("el => getComputedStyle(el).borderTopColor")
        color = delete_button.evaluate("el => getComputedStyle(el).color")
        border_radius = delete_button.evaluate(
            "el => getComputedStyle(el).borderRadius"
        )

        # --color-error: #B00020 -> rgb(176, 0, 32)
        assert border == "rgb(176, 0, 32)"
        assert color == "rgb(176, 0, 32)"
        assert border_radius == "0px"

    def test_pagination_buttons_use_secondary_style(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        next_button = page.get_by_role("button", name="下一頁")
        next_button.wait_for()

        border = next_button.evaluate("el => getComputedStyle(el).borderTopColor")
        color = next_button.evaluate("el => getComputedStyle(el).color")
        border_radius = next_button.evaluate(
            "el => getComputedStyle(el).borderRadius"
        )

        assert border == "rgb(17, 17, 17)"
        assert color == "rgb(17, 17, 17)"
        assert border_radius == "0px"


class TestArticlesListFocusVisibleOutlineE2E:
    """AC4/§8: Tab 到編輯連結/刪除按鈕/分頁按鈕顯示可見 focus 樣式。"""

    def test_delete_button_shows_visible_focus_outline_on_keyboard_nav(
        self, page: Page, frontend_preview_server: str
    ) -> None:
        _seed_articles_route(page)
        _goto_authenticated_articles_page(page, frontend_preview_server)

        delete_button = page.get_by_test_id("delete-article-1")
        delete_button.wait_for()
        delete_button.focus()

        outline_style = delete_button.evaluate(
            "el => getComputedStyle(el).outlineStyle"
        )
        outline_width = delete_button.evaluate(
            "el => getComputedStyle(el).outlineWidth"
        )

        assert outline_style == "solid"
        assert outline_width == "2px"
