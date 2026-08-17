"""Real Playwright e2e coverage for SDLCAIP1-20's responsive article detail
static page.

Unlike the admin SPA e2e suite (test_login_flow_e2e.py, etc.) this story's
output is not part of `frontend/` — it's a plain static HTML file generated
by `_generate_and_upload_static_page` (src/cms_aipilot/main.py) and uploaded
to S3, served directly to site visitors. There is no build/dev server to
stand up for it, so this suite generates the exact HTML string the function
would upload (S3 mocked, same as tests/test_article_detail_page.py) and
loads it into a real browser, then asserts on actual rendered/computed
layout at each of the three breakpoints named in the acceptance criteria —
something a string-level pytest assertion cannot verify (horizontal scroll,
single-column flow, centered max-width).

Since SDLCAIP1-34, the page's `<head>` links an external
`/design-tokens.css` stylesheet (SDLCAIP1-30). A page loaded via
`page.set_content` has `about:blank` as its origin, so that relative
`<link>` never actually issues a request and the stylesheet never loads --
same root cause as test_search_page_e2e.py's `/search/index.json` fetch
issue. We use the same fake-https-URL + `page.route`/`page.goto`
interception pattern here instead.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from playwright.sync_api import Page, Route

from cms_aipilot.main import _DESIGN_TOKENS_PATH, Article, _generate_and_upload_static_page

MOBILE_WIDTH = 375
TABLET_WIDTH = 900
DESKTOP_WIDTH = 1280
VIEWPORT_HEIGHT = 800

ARTICLE_PAGE_URL = "https://e2e-article-page.example/articles/a1.html"
DESIGN_TOKENS_URL = "https://e2e-article-page.example/design-tokens.css"


def _generated_html(monkeypatch, article: Article) -> str:
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        _generate_and_upload_static_page(article)
    return fake_s3.put_object.call_args.kwargs["Body"]


def _load_article_page(page: Page, monkeypatch, article: Article) -> None:
    """Loads the generated article detail page into the browser with
    `/design-tokens.css` intercepted to return the real stylesheet content
    (read directly from `_DESIGN_TOKENS_PATH`, not via
    `_generate_and_upload_design_tokens()` -- that function's job is
    uploading to S3, an unrelated side effect this suite doesn't need)."""
    html = _generated_html(monkeypatch, article)

    with open(_DESIGN_TOKENS_PATH, encoding="utf-8") as f:
        design_tokens_css = f.read()

    def handle_page(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=html)

    def handle_design_tokens(route: Route) -> None:
        route.fulfill(status=200, content_type="text/css", body=design_tokens_css)

    page.route(ARTICLE_PAGE_URL, handle_page)
    page.route("**/design-tokens.css", handle_design_tokens)

    page.goto(ARTICLE_PAGE_URL)


def _no_horizontal_scroll(page: Page) -> bool:
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


class TestArticleDetailPageFullContentRendersInBrowser:
    """Scenario: 文章詳細頁顯示完整內容"""

    def test_title_content_and_published_time_visible(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1",
            title="E2E Article Title",
            content="E2E full plain-text article body.",
            published_at="2026-08-10T09:30:00",
        )
        _load_article_page(page, monkeypatch, article)

        assert page.get_by_text("E2E Article Title").is_visible()
        assert page.get_by_text("E2E full plain-text article body.").is_visible()
        assert page.get_by_text("2026-08-10 09:30").is_visible()


class TestArticleDetailPageMobileLayout:
    """Scenario: 手機寬度版面正常顯示（<768px）-> 單欄、無橫向捲動、不溢出"""

    def test_single_column_no_horizontal_scroll(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1",
            title="Mobile Title",
            content="Mobile body content " * 20,
            published_at="2026-01-01T00:00:00",
        )
        page.set_viewport_size({"width": MOBILE_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)

        assert _no_horizontal_scroll(page)
        article_box = page.locator(".article").bounding_box()
        assert article_box is not None
        assert article_box["width"] <= MOBILE_WIDTH

    def test_long_unbroken_word_does_not_overflow(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1",
            title="Mobile Title",
            content="a" * 300,  # single unbroken "word"
            published_at="2026-01-01T00:00:00",
        )
        page.set_viewport_size({"width": MOBILE_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)

        assert _no_horizontal_scroll(page)


class TestArticleDetailPageTabletLayout:
    """Scenario: 平板寬度版面正常顯示（768px–1024px）-> 版面依平板寬度調整、無橫向捲動"""

    def test_no_horizontal_scroll_at_tablet_width(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1",
            title="Tablet Title",
            content="Tablet body content " * 20,
            published_at="2026-01-01T00:00:00",
        )
        page.set_viewport_size({"width": TABLET_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)

        assert _no_horizontal_scroll(page)

    def test_tablet_body_padding_differs_from_mobile(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )

        page.set_viewport_size({"width": MOBILE_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)
        mobile_padding = page.evaluate(
            "getComputedStyle(document.body).paddingLeft"
        )

        page.set_viewport_size({"width": TABLET_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)
        tablet_padding = page.evaluate(
            "getComputedStyle(document.body).paddingLeft"
        )

        assert tablet_padding != mobile_padding


class TestArticleDetailPageDesktopLayout:
    """Scenario: 桌機寬度版面正常顯示（>1024px）-> 內容最大寬度限制、置中、無橫向捲動"""

    def test_no_horizontal_scroll_at_desktop_width(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1",
            title="Desktop Title",
            content="Desktop body content " * 20,
            published_at="2026-01-01T00:00:00",
        )
        page.set_viewport_size({"width": DESKTOP_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)

        assert _no_horizontal_scroll(page)

    def test_content_max_width_and_centered(self, page: Page, monkeypatch) -> None:
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        page.set_viewport_size({"width": DESKTOP_WIDTH, "height": VIEWPORT_HEIGHT})
        _load_article_page(page, monkeypatch, article)

        article_box = page.locator(".article").bounding_box()
        assert article_box is not None
        # Max-width capped well below the full viewport width.
        assert article_box["width"] <= 800
        # Roughly centered: left/right gaps to the viewport edges are close.
        left_gap = article_box["x"]
        right_gap = DESKTOP_WIDTH - (article_box["x"] + article_box["width"])
        assert abs(left_gap - right_gap) < 5


class TestArticleDetailPageEscapingRendersAsText:
    """Scenario: 文章內容含特殊字元時正確逸出 -> 不造成標籤注入"""

    def test_special_characters_render_as_visible_text_not_injected_markup(
        self, page: Page, monkeypatch
    ) -> None:
        article = Article(
            id="a1",
            title='<script>window.__injected = true</script> & "quoted"',
            content='<img src=x onerror="window.__injected2 = true"> plain & text',
            published_at="2026-01-01T00:00:00",
        )
        _load_article_page(page, monkeypatch, article)

        # No script/img injection actually executed or rendered as an element.
        assert page.evaluate("window.__injected") is None
        assert page.evaluate("window.__injected2") is None
        assert page.locator("img").count() == 0
        assert page.locator("script:not([type])").count() == 0

        # The special characters are visible as literal text content instead.
        assert page.get_by_text('"quoted"').is_visible()
        assert page.get_by_text("plain & text").is_visible()


class TestArticleDetailPageDesignTokensApplied:
    """Scenario: 文章詳細頁套用 design-tokens.css 色彩/字體/對齊規範（SDLCAIP1-34）"""

    def test_design_tokens_are_applied_to_computed_styles(
        self, page: Page, monkeypatch
    ) -> None:
        article = Article(
            id="a1",
            title="Token Title",
            content="Token body content.",
            published_at="2026-01-01T00:00:00",
        )
        _load_article_page(page, monkeypatch, article)

        meta_color = page.evaluate(
            "getComputedStyle(document.querySelector('.article__meta')).color"
        )
        assert meta_color == "rgb(17, 17, 17)"

        body_font_family = page.evaluate(
            "getComputedStyle(document.body).fontFamily"
        )
        assert "PingFang TC" in body_font_family

        title_text_align = page.evaluate(
            "getComputedStyle(document.querySelector('.article__title')).textAlign"
        )
        meta_text_align = page.evaluate(
            "getComputedStyle(document.querySelector('.article__meta')).textAlign"
        )
        assert title_text_align == "center"
        assert meta_text_align == "center"

        content_text_align = page.evaluate(
            "getComputedStyle(document.querySelector('.article__content')).textAlign"
        )
        assert content_text_align == "left"
