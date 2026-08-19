"""Unit-level regression coverage for SDLCAIP1-36's design-token styling of
the front-end search page (search.html), complementing the Playwright e2e
suite in `tests/e2e/test_search_page_design_tokens_e2e.py`.

The e2e suite verifies *computed* styles in a real browser (the ground
truth for what a visitor sees), but computed-style assertions alone don't
pin down *where* a rule lives in the source, or that a rule was never
written at all (as opposed to being overridden by something later in the
cascade). This file adds cheap, browser-free guards for exactly those
gaps:

- AC1: the `<link>` tag's literal string presence/placement in the
  generated HTML (not just that the browser resolved it -- the e2e suite
  proves resolution, this proves the source emits the correct tag).
- AC3: `.article-list__item`/`.article-list__link` rules live inside
  `_SEARCH_PAGE_STYLE` specifically (not a new constant, not
  `_LIST_PAGE_STYLE` -- the ticket's dependency-isolation requirement is a
  source-location property that computed-style assertions can't detect:
  a test could pass in the browser today and still be silently
  drawing the values from `_LIST_PAGE_STYLE` if the two constants ever
  diverge, which is exactly the coupling AC3 forbids), and that no
  border/box-shadow/background-color declaration was ever written for
  `.article-list__item` (regression guard -- a browser default can look
  identical to an explicit `none`/`transparent` override in a computed
  style, but only the *absence* of the declaration matches the design
  doc's "no card affordance" decision; an explicit
  `border: none`/`background: transparent` would pass the e2e assertions
  while still contradicting the spec's "don't add these rules" framing).
- AC4: the client-side script never renders `item.content` (the article
  body used only for keyword matching) into any DOM text/HTML -- the e2e
  suite proves the *rendered* title-only text for one specific fixture,
  this proves no code path in the script could ever inject content text.
- AC5: `--color-error` is not even defined in `design-tokens.css`, and no
  `.search-empty`/`#search-empty` color rule was added anywhere in
  `_SEARCH_PAGE_STYLE`.

Self-contained per this repo's `tests/e2e/` convention (no
`tests/__init__.py` exists, so cross-file `from tests....import` breaks
collection for the whole suite) -- no fixtures/constants are imported from
other test files.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cms_aipilot.main import (
    _DESIGN_TOKENS_PATH,
    _LIST_PAGE_STYLE,
    _SEARCH_PAGE_SCRIPT,
    _SEARCH_PAGE_STYLE,
    _generate_and_upload_search_page,
)


def _generated_body(monkeypatch) -> str:
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        _generate_and_upload_search_page()
    return fake_s3.put_object.call_args.kwargs["Body"]


class TestDesignTokensStylesheetLinkInHead:
    """AC1: `<head>` contains the absolute-path stylesheet `<link>`, placed
    after the existing `<style>` block and before `</head>` (per the
    design doc's head diff, matching `_render_list_page_html`'s existing
    placement convention)."""

    def test_link_tag_present_with_absolute_href(self, monkeypatch):
        body = _generated_body(monkeypatch)
        assert '<link rel="stylesheet" href="/design-tokens.css">' in body

    def test_link_tag_is_after_style_block_and_before_head_close(self, monkeypatch):
        body = _generated_body(monkeypatch)
        style_close_index = body.index("</style>")
        link_index = body.index('<link rel="stylesheet" href="/design-tokens.css">')
        head_close_index = body.index("</head>")
        assert style_close_index < link_index < head_close_index


class TestArticleListRulesLiveInSearchPageStyleOnly:
    """AC3: `.article-list__item`/`.article-list__link` styling for the
    search page is defined inside `_SEARCH_PAGE_STYLE` itself -- not a new
    standalone constant, and with zero code-level coupling to
    `_LIST_PAGE_STYLE` (SDLCAIP1-35's scope)."""

    def test_search_page_style_defines_article_list_item_and_link(self):
        assert ".article-list__item" in _SEARCH_PAGE_STYLE
        assert ".article-list__link" in _SEARCH_PAGE_STYLE

    def test_search_page_generation_never_references_list_page_style(self, monkeypatch):
        """The generated search.html body must not be built from
        `_LIST_PAGE_STYLE` in any way -- proves AC3's "must not depend on
        SDLCAIP1-35's `_LIST_PAGE_STYLE` change" at the source level, not
        just by coincidentally-equal computed values."""
        body = _generated_body(monkeypatch)
        assert _LIST_PAGE_STYLE not in body

    def test_article_list_item_has_no_border_box_shadow_or_background_rule(self):
        """Regression guard for the design doc's explicit 'no card
        affordance' decision (design-system.md §7): assert the source
        style block never declares these properties at all for
        `.article-list__item`, distinguishing 'never written' from 'written
        as none/transparent' -- both look identical to the e2e suite's
        computed-style assertions but only the former matches the spec."""
        item_block = _SEARCH_PAGE_STYLE.split(".article-list__item")[1].split("}")[0]
        assert "border" not in item_block
        assert "box-shadow" not in item_block
        assert "background" not in item_block


class TestSearchResultsNeverRenderArticleContent:
    """AC4: search results are title-only; the client-side script must
    never place `item.content` (the article body used only for keyword
    matching) into any DOM text or HTML."""

    def test_script_only_reads_content_for_matching_not_rendering(self):
        matching_line = 'item.content.toLowerCase().indexOf(lowerKeyword) !== -1'
        assert matching_line in _SEARCH_PAGE_SCRIPT

        # Split out the rendering section (matches.forEach onward) and
        # confirm it never touches item.content -- only item.id/item.title.
        render_section = _SEARCH_PAGE_SCRIPT.split("matches.forEach")[1]
        assert "item.content" not in render_section
        assert "item.title" in render_section

    def test_body_has_no_excerpt_or_summary_related_markup(self, monkeypatch):
        body = _generated_body(monkeypatch)
        assert "excerpt" not in body.lower()
        assert "summary" not in body.lower()


class TestNoErrorColorAppliedToSearchEmptyMessage:
    """AC5: `--color-error` is not applied to `#search-empty` -- verified
    both by confirming the token isn't even defined in
    `design-tokens.css`, and that `_SEARCH_PAGE_STYLE` never adds a color
    rule for the empty-state selector."""

    def test_color_error_token_not_defined_in_design_tokens_css(self):
        with open(_DESIGN_TOKENS_PATH, encoding="utf-8") as f:
            tokens_css = f.read()
        assert "--color-error" not in tokens_css

    def test_search_page_style_has_no_search_empty_color_rule(self):
        assert ".search-empty" not in _SEARCH_PAGE_STYLE
        assert "#search-empty" not in _SEARCH_PAGE_STYLE
