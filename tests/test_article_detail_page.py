"""Tests for SDLCAIP1-20's responsive article detail static page output.

Exercises `_generate_and_upload_static_page` directly (with S3 mocked, same
pattern as the SDLCAIP1-8/9 tests in tests/test_articles.py) and inspects the
generated HTML string for each Gherkin acceptance criterion.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cms_aipilot.main import Article, _generate_and_upload_static_page


@pytest.fixture
def mock_s3(monkeypatch):
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        yield fake_s3


def _generated_body(mock_s3, article: Article) -> str:
    _generate_and_upload_static_page(article)
    mock_s3.put_object.assert_called_once()
    return mock_s3.put_object.call_args.kwargs["Body"]


class TestArticleDetailPageFullContent:
    """Scenario: 文章詳細頁顯示完整內容 -> 頁面顯示文章標題、內文全文、發布時間"""

    def test_title_content_and_published_at_present_in_html(self, mock_s3):
        article = Article(
            id="article-1",
            title="Hello World",
            content="Full plain-text article body goes here.",
            published_at="2026-08-10T09:30:00",
        )
        body = _generated_body(mock_s3, article)

        assert "Hello World" in body
        assert "Full plain-text article body goes here." in body
        # Human-readable published time.
        assert "2026-08-10 09:30" in body
        # Machine-readable <time datetime="..."> for the same timestamp.
        assert '<time class="article__meta" datetime="2026-08-10T09:30:00">' in body

    def test_content_type_is_text_html(self, mock_s3):
        article = Article(
            id="article-1",
            title="T",
            content="C",
            published_at="2026-01-01T00:00:00",
        )
        _generate_and_upload_static_page(article)
        assert mock_s3.put_object.call_args.kwargs["ContentType"] == "text/html"


class TestArticleDetailPageResponsiveLayoutMarkup:
    """Scenarios: 手機/平板/桌機寬度版面 -> generated HTML carries the viewport
    meta tag and CSS media queries at the 768px/1024px breakpoints needed for
    responsive rendering. Actual rendered-layout assertions (no horizontal
    scroll, single column, centered max-width) are covered by the real
    browser Playwright e2e test in tests/e2e/test_article_detail_page_e2e.py
    — a string-level check here can't observe computed CSS layout.
    """

    def test_viewport_meta_tag_present(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in body

    def test_mobile_default_styles_single_column_no_overflow(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        # Base (mobile-first) rules: full-width article block, word wrapping
        # so long unbroken content can't force horizontal scroll.
        assert "overflow-wrap: break-word" in body
        assert ".article { max-width: 100%; }" in body

    def test_tablet_breakpoint_media_query_present(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        assert "@media (min-width: 768px) and (max-width: 1024px)" in body

    def test_desktop_breakpoint_media_query_with_centered_max_width(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        assert "@media (min-width: 1025px)" in body
        assert ".article { max-width: 800px; margin: 0 auto; }" in body


class TestArticleDetailPageDesignTokensMarkup:
    """Scenario: 文章詳細頁套用 design-tokens.css 色彩/字體/對齊規範
    (SDLCAIP1-34) -- string-level checks on the generated HTML/CSS that the
    real-browser computed-style assertions in
    tests/e2e/test_article_detail_page_e2e.py::TestArticleDetailPageDesignTokensApplied
    complement but do not fully cover (that suite only asserts computed
    color for .article__meta, not .article__title/.article__content, and
    can't tell `var(--color-text-primary)` apart from
    `var(--color-text-secondary)` since both currently resolve to the same
    hex value in design-tokens.css).
    """

    def test_design_tokens_stylesheet_link_present_between_title_and_style(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)

        link_tag = '<link rel="stylesheet" href="/design-tokens.css">'
        assert link_tag in body
        title_idx = body.index("<title>T</title>")
        link_idx = body.index(link_tag)
        style_idx = body.index("<style>")
        assert title_idx < link_idx < style_idx

    def test_title_and_content_use_text_primary_color_token(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)

        assert (
            '.article__title { font-size: 1.5rem; margin: 0 0 var(--space-2); '
            'color: var(--color-text-primary); text-align: center; }'
        ) in body
        assert (
            '.article__content { white-space: pre-wrap; '
            'color: var(--color-text-primary); text-align: left; }'
        ) in body

    def test_meta_uses_text_secondary_color_token_not_hardcoded_hex(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)

        assert "var(--color-text-secondary)" in body
        assert "#666" not in body

    def test_body_uses_font_family_base_token_not_hardcoded_stack(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)

        assert "font-family: var(--font-family-base);" in body
        assert "system-ui" not in body

    def test_title_and_meta_centered_content_left_aligned(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)

        assert '.article__title { font-size: 1.5rem; margin: 0 0 var(--space-2); color: var(--color-text-primary); text-align: center; }' in body
        assert '.article__meta { display: block; color: var(--color-text-secondary); font-size: 0.875rem; margin-bottom: var(--space-4); text-align: center; }' in body
        assert '.article__content { white-space: pre-wrap; color: var(--color-text-primary); text-align: left; }' in body


class TestArticleDetailPageBackToListLink:
    """Scenario (SDLCAIP1-40): 文章詳細頁顯示返回首頁的連結 -> 頁面上有一個連到
    "/" 的連結，文字清楚可辨識；且與既有「搜尋文章」連結並存，不互相取代。
    """

    def test_back_to_list_link_present(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        assert '<a href="/">回文章列表</a>' in body

    def test_back_to_list_link_coexists_with_search_link(self, mock_s3):
        article = Article(
            id="a1", title="T", content="C", published_at="2026-01-01T00:00:00"
        )
        body = _generated_body(mock_s3, article)
        assert '<a href="/">回文章列表</a>' in body
        assert '<a href="/search.html">搜尋文章</a>' in body


class TestArticleDetailPageEscaping:
    """Scenario: 文章內容含特殊字元時正確逸出 -> 不造成標籤注入"""

    def test_html_special_characters_in_title_and_content_are_escaped(self, mock_s3):
        article = Article(
            id="a1",
            title='<script>alert("t")</script> & "quoted"',
            content='<img src=x onerror=alert(1)> & "double quotes" & <b>bold</b>',
            published_at="2026-01-01T00:00:00",
        )
        body = _generated_body(mock_s3, article)

        assert "<script>" not in body
        assert "<img" not in body
        assert "<b>bold</b>" not in body
        assert "&lt;script&gt;" in body
        assert "&lt;img" in body
        assert "&amp;" in body
        assert "&quot;" in body

    def test_no_raw_less_than_sign_in_user_supplied_portions(self, mock_s3):
        article = Article(
            id="a1",
            title="a < b",
            content="c < d",
            published_at="2026-01-01T00:00:00",
        )
        body = _generated_body(mock_s3, article)
        assert "a < b" not in body
        assert "c < d" not in body
        assert "a &lt; b" in body
        assert "c &lt; d" in body
