"""Real Playwright e2e coverage for SDLCAIP1-36's design-token styling of
the front-end search page (search.html).

Companion to `test_search_page_e2e.py` (SDLCAIP1-28/26/27 search behaviour),
deliberately kept in a separate file per the SDLCAIP1-36 design doc so the
existing suite stays untouched. This story's `<head>` now references an
external stylesheet (`<link rel="stylesheet" href="/design-tokens.css">`),
which `page.set_content()` cannot exercise -- a page loaded via
`set_content` sits at the `about:blank` origin, which has no base to resolve
the absolute `/design-tokens.css` URL against, so the browser never issues
(and Playwright can never intercept) that stylesheet request. Instead, like
`test_articles_list_page_styling_e2e.py` (SDLCAIP1-35) and
`test_article_detail_page_e2e.py` (SDLCAIP1-34), we intercept a fake https
origin with `page.route(...)` + `page.goto(...)`, routing the search page
URL to the generated HTML and `/design-tokens.css` to the real token file
content (read from `cms_aipilot.main._DESIGN_TOKENS_PATH` -- not a
hand-copied literal, so this test can't silently drift out of sync with the
real file).

`SEARCH_INDEX`/`SEARCH_PAGE_URL`/`_generated_html` are defined locally
below, mirroring `test_search_page_e2e.py`'s own definitions, rather than
importing them cross-file -- this repo has no `tests/__init__.py`, so a
`from tests.e2e.test_search_page_e2e import ...` package-style import fails
at collection time (`ModuleNotFoundError: No module named 'tests'`) under
pytest's default rootless import mode, which interrupts collection of the
*entire* suite, not just this file.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from playwright.sync_api import Page, Route

from cms_aipilot.main import _DESIGN_TOKENS_PATH, _generate_and_upload_search_page

SEARCH_INDEX = [
    {
        "id": "a1",
        "title": "Sunrise over the mountains",
        "content": "A quiet plain-text article body about hiking trails.",
        "published_at": "2026-01-01T00:00:00",
    },
    {
        "id": "a2",
        "title": "Unrelated headline",
        "content": "This body mentions a Keyword somewhere in the middle of it.",
        "published_at": "2026-01-02T00:00:00",
    },
]


def _generated_html(monkeypatch) -> str:
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        _generate_and_upload_search_page()
    return fake_s3.put_object.call_args.kwargs["Body"]


SEARCH_PAGE_URL = "https://e2e-search-page.example/search.html"


def _load_with_tokens(page: Page, monkeypatch, index_data: list[dict]) -> None:
    """Loads the generated search.html with both `/design-tokens.css` and
    `/search/index.json` intercepted, then triggers a search that matches at
    least one result so `.article-list__item`/`.article-list__link` have
    content to assert against."""
    html = _generated_html(monkeypatch)
    with open(_DESIGN_TOKENS_PATH, encoding="utf-8") as f:
        tokens_css = f.read()

    def handle_page(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=html)

    def handle_tokens(route: Route) -> None:
        route.fulfill(status=200, content_type="text/css", body=tokens_css)

    def handle_index(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(index_data),
        )

    page.route(SEARCH_PAGE_URL, handle_page)
    page.route("**/design-tokens.css", handle_tokens)
    page.route("**/search/index.json", handle_index)

    page.goto(SEARCH_PAGE_URL)
    page.wait_for_timeout(100)


class TestSearchFormInputSpacingUsesDesignTokens:
    """AC2: `.search-form__input` padding/margin-bottom switch to
    var(--space-*) tokens but resolve to the same px values as before."""

    def test_input_padding_and_margin_bottom_unchanged_px_values(
        self, page: Page, monkeypatch
    ) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        input_el = page.locator("#search-input")
        padding = input_el.evaluate("el => getComputedStyle(el).padding")
        margin_bottom = input_el.evaluate("el => getComputedStyle(el).marginBottom")

        # --space-2: 8px, --space-3: 12px -> unchanged from literal 8px 12px
        assert padding == "8px 12px"
        # --space-4: 16px -> unchanged from literal 16px
        assert margin_bottom == "16px"


class TestArticleListItemHasNoBorderShadowOrBackground:
    """AC3: search-result `.article-list__item` has no
    border/box-shadow/background-color."""

    def test_item_has_no_border_shadow_or_background(self, page: Page, monkeypatch) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        page.fill("#search-input", "Sunrise")

        item = page.locator(".article-list__item")
        border_bottom_width = item.evaluate("el => getComputedStyle(el).borderBottomWidth")
        box_shadow = item.evaluate("el => getComputedStyle(el).boxShadow")
        background_color = item.evaluate("el => getComputedStyle(el).backgroundColor")

        assert border_bottom_width == "0px"
        assert box_shadow == "none"
        assert background_color == "rgba(0, 0, 0, 0)"


class TestArticleListLinkColorAndAlignment:
    """AC3: search-result `.article-list__link` uses
    var(--color-text-primary) and the item's title is centered."""

    def test_link_color_uses_text_primary_token(self, page: Page, monkeypatch) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        page.fill("#search-input", "Sunrise")

        link = page.locator(".article-list__link")
        color = link.evaluate("el => getComputedStyle(el).color")

        # --color-text-primary: #111111 -> rgb(17, 17, 17)
        assert color == "rgb(17, 17, 17)"

    def test_item_text_align_center(self, page: Page, monkeypatch) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        page.fill("#search-input", "Sunrise")

        item = page.locator(".article-list__item")
        assert item.evaluate("el => getComputedStyle(el).textAlign") == "center"


class TestSearchResultsRenderTitleOnly:
    """AC4: search results render title-only, no excerpt/summary text."""

    def test_result_link_text_is_title_only(self, page: Page, monkeypatch) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        page.fill("#search-input", "hiking trails")

        link = page.locator(".article-list__link")
        assert link.text_content() == "Sunrise over the mountains"


class TestSearchEmptyMessageHasNoErrorColor:
    """AC5: `#search-empty` gets no color rule at all -- design-tokens.css
    doesn't even define `--color-error`, so it just falls back to the
    browser's default inherited text color, not any red/error color."""

    def test_empty_message_color_is_not_red(self, page: Page, monkeypatch) -> None:
        _load_with_tokens(page, monkeypatch, SEARCH_INDEX)

        page.fill("#search-input", "nonexistent-keyword-xyz")

        empty_message = page.locator("#search-empty")
        assert empty_message.is_visible()
        color = empty_message.evaluate("el => getComputedStyle(el).color")

        # Should be plain black (browser/user-agent default), not a red tone.
        assert color == "rgb(0, 0, 0)"
