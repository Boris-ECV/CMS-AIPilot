"""Tests for SDLCAIP1-30's shared visual style token stylesheet
(design-tokens.css).

Exercises `_generate_and_upload_design_tokens` directly (S3 mocked, same
pattern as tests/test_search_page.py) and the create/update/delete
endpoints end-to-end to verify the integration points wire in the new
call. This file asserts the backend orchestration (upload key/content-type,
failure handling, rollback) is correct; the exact CSS custom property
values are the responsibility of docs/design-system.md and the static
file itself (docs/design/SDLCAIP1-30.md 介面/API 契約).
"""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from cms_aipilot.main import (
    DESIGN_TOKENS_KEY,
    StaticPageGenerationError,
    _generate_and_upload_design_tokens,
    app,
)

client = TestClient(app, headers={"Authorization": "Bearer test-token"})

VALID_PAYLOAD = {
    "title": "Hello World",
    "content": "Some article content.",
    "published_at": "2026-08-10T09:00:00",
}


@pytest.fixture(autouse=True)
def mock_auth():
    with patch(
        "cms_aipilot.main.decode_access_token", return_value={"sub": "admin"}
    ) as mocked:
        yield mocked


@pytest.fixture
def mock_table():
    fake_table = MagicMock()
    with patch("cms_aipilot.main.get_articles_table", return_value=fake_table):
        yield fake_table


@pytest.fixture
def mock_s3(monkeypatch):
    monkeypatch.setenv("ARTICLES_STATIC_BUCKET_NAME", "test-articles-static-bucket")
    fake_s3 = MagicMock()
    with patch("cms_aipilot.main.get_s3_client", return_value=fake_s3):
        yield fake_s3


class TestDesignTokensKey:
    def test_key_is_design_tokens_css_at_bucket_root(self):
        assert DESIGN_TOKENS_KEY == "design-tokens.css"


class TestGenerateAndUploadDesignTokens:
    """Unit tests for the standalone stylesheet upload function."""

    def test_uploads_to_design_tokens_css_with_text_css_content_type(self, mock_s3):
        _generate_and_upload_design_tokens()

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-articles-static-bucket"
        assert call_kwargs["Key"] == "design-tokens.css"
        assert call_kwargs["ContentType"] == "text/css"

    def test_body_contains_root_selector_and_known_tokens(self, mock_s3):
        _generate_and_upload_design_tokens()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        assert ":root {" in body
        assert "--color-bg: #FFFFFF;" in body
        assert "--color-text-primary: #111111;" in body
        assert "--space-4: 16px;" in body
        assert "--breakpoint-tablet-min: 768px;" in body

    def test_body_contains_every_token_from_design_system_md_with_exact_values(self, mock_s3):
        """AC1 (Gherkin): 'design-tokens.css 內容包含 docs/design-system.md 第
        1-5 節定義的全部 CSS 自訂屬性，數值完全一致' — the spot-check test
        above only samples 4 of the ~24 tokens. This test asserts the
        *complete* set defined in docs/design-system.md §1-5 (色彩/字體/間距/
        斷點), values copied verbatim from that document, so a regression
        that silently drops or mis-values any single token is caught."""
        _generate_and_upload_design_tokens()
        body = mock_s3.put_object.call_args.kwargs["Body"]

        expected_declarations = [
            # §1 色彩系統
            "--color-bg: #FFFFFF;",
            "--color-text-primary: #111111;",
            "--color-text-secondary: #111111;",
            "--color-border: #E5E5E5;",
            # §2 字體
            '--font-family-base: -apple-system, BlinkMacSystemFont, "PingFang TC",',
            '"Noto Sans TC", sans-serif;',
            # §3 字級與字重階層
            "--font-size-display: 2.5rem;",
            "--line-height-display: 1.3;",
            "--font-weight-display: 400;",
            "--font-size-h1: 2rem;",
            "--line-height-h1: 1.35;",
            "--font-weight-h1: 600;",
            "--font-size-h2: 1.5rem;",
            "--line-height-h2: 1.4;",
            "--font-weight-h2: 600;",
            "--font-size-body: 1rem;",
            "--line-height-body: 1.7;",
            "--font-weight-body: 400;",
            "--font-size-meta: 0.875rem;",
            "--line-height-meta: 1.5;",
            "--font-weight-meta: 400;",
            "--font-size-nav: 0.9375rem;",
            "--line-height-nav: 1.5;",
            "--font-weight-nav: 400;",
            # §4 間距 Scale
            "--space-1: 4px;",
            "--space-2: 8px;",
            "--space-3: 12px;",
            "--space-4: 16px;",
            "--space-5: 24px;",
            "--space-6: 32px;",
            "--space-7: 48px;",
            "--space-8: 64px;",
            # §5 RWD 斷點
            "--breakpoint-tablet-min: 768px;",
            "--breakpoint-tablet-max: 1024px;",
            "--breakpoint-desktop-min: 1025px;",
        ]
        for declaration in expected_declarations:
            assert declaration in body, f"missing or mismatched token declaration: {declaration!r}"

        # §1 also documents that --color-accent is deliberately undefined
        # (design-system.md: "本風格核心特徵：不設強調色") — assert there is
        # no actual custom-property *declaration* for it (a mention in an
        # explanatory comment, as the file has, is fine and expected).
        assert "--color-accent:" not in body

    def test_frontend_copy_is_byte_identical_to_backend_static_copy(self, mock_s3):
        """Both `src/cms_aipilot/static/design-tokens.css` (uploaded to S3,
        asserted above) and `frontend/src/styles/design-tokens.css`
        (imported by LoginPage.tsx, AC3) are meant to share the same base
        §1-5 token values per docs/design/SDLCAIP1-30.md 關鍵技術決策. This
        guards against the two hand-maintained copies drifting apart.

        Frontend may additionally define documented functional-color
        exceptions (docs/design-system.md §1's exception clause) that the
        backend-rendered static pages don't need — e.g. `--color-error`,
        added by docs/design/SDLCAIP1-31.md and SDLCAIP1-33.md for
        admin-UI-only form validation styling. FRONTEND_ONLY_TOKENS is the
        explicit allowlist of such exceptions; every other custom property
        must still match exactly between the two files."""
        _generate_and_upload_design_tokens()
        backend_body = mock_s3.put_object.call_args.kwargs["Body"]

        frontend_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "styles", "design-tokens.css"
        )
        with open(frontend_path, encoding="utf-8") as f:
            frontend_body = f.read()

        FRONTEND_ONLY_TOKENS = {"--color-error"}

        def parse_tokens(css_text: str) -> dict[str, str]:
            return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", css_text))

        backend_tokens = parse_tokens(backend_body)
        frontend_tokens = parse_tokens(frontend_body)

        frontend_only = set(frontend_tokens) - set(backend_tokens)
        assert frontend_only <= FRONTEND_ONLY_TOKENS, (
            f"undocumented frontend-only token(s), add to FRONTEND_ONLY_TOKENS "
            f"if intentional: {frontend_only - FRONTEND_ONLY_TOKENS}"
        )
        shared_frontend_tokens = {
            k: v for k, v in frontend_tokens.items() if k not in FRONTEND_ONLY_TOKENS
        }
        assert backend_tokens == shared_frontend_tokens

    def test_upload_failure_raises_static_page_generation_error(self, mock_s3):
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
        )
        with pytest.raises(StaticPageGenerationError) as exc_info:
            _generate_and_upload_design_tokens()
        assert exc_info.value.article_id == "design-tokens"

    def test_read_failure_raises_static_page_generation_error(self, mock_s3):
        with (
            patch("cms_aipilot.main._DESIGN_TOKENS_PATH", "/nonexistent/path.css"),
            pytest.raises(StaticPageGenerationError) as exc_info,
        ):
            _generate_and_upload_design_tokens()
        assert exc_info.value.article_id == "design-tokens"
        mock_s3.put_object.assert_not_called()


class TestCreateArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_create(self, mock_table, mock_s3):
        mock_table.scan.return_value = {"Items": []}
        response = client.post("/articles", json=VALID_PAYLOAD)
        assert response.status_code == 201

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_and_rolls_back_when_design_tokens_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.post("/articles", json=VALID_PAYLOAD)

        assert response.status_code == 502
        assert response.json() == {
            "error": "STATIC_PAGE_GENERATION_FAILED",
            "message": "Article could not be published: static page upload failed.",
        }
        article_id = mock_table.put_item.call_args.kwargs["Item"]["id"]
        mock_table.delete_item.assert_called_once_with(Key={"id": article_id})


class TestUpdateArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_update(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 200

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_when_design_tokens_upload_fails(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.put("/articles/a1", json=VALID_PAYLOAD)
        assert response.status_code == 502
        mock_table.delete_item.assert_called_once_with(Key={"id": "a1"})


class TestDeleteArticleTriggersDesignTokensUpload:
    def test_design_tokens_uploaded_after_delete(self, mock_table, mock_s3):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        response = client.delete("/articles/a1")
        assert response.status_code == 204

        keys = [c.kwargs["Key"] for c in mock_s3.put_object.call_args_list]
        assert "design-tokens.css" in keys

    def test_returns_502_with_dedicated_error_code_when_design_tokens_upload_fails(
        self, mock_table, mock_s3
    ):
        mock_table.get_item.return_value = {"Item": {"id": "a1"}}
        mock_table.scan.return_value = {"Items": []}

        def put_object_side_effect(**kwargs):
            if kwargs["Key"] != "design-tokens.css":
                return
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
            )

        mock_s3.put_object.side_effect = put_object_side_effect

        response = client.delete("/articles/a1")
        assert response.status_code == 502
        assert response.json()["error_code"] == "STATIC_DESIGN_TOKENS_REGENERATION_FAILED"
