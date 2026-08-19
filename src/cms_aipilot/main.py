import html
import json
import logging
import math
import os
import time
import uuid
from datetime import datetime

import bcrypt
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel, Field

from cms_aipilot.auth import (
    create_access_token,
    decode_access_token,
    get_admin_password_hash,
    get_admin_username,
)

app = FastAPI(title="CMS AI Pilot")

logger = logging.getLogger(__name__)

AUTH_STATE_ID = "admin_login_state"
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION_SECONDS = 15 * 60

# Fixed dummy bcrypt hash used when the supplied username doesn't match the
# admin username, so bcrypt.checkpw is always invoked (constant-time-ish
# response regardless of whether the username exists) and the endpoint
# doesn't leak valid usernames via a timing side-channel.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"dummy-password-for-timing-safety-do-not-use", bcrypt.gensalt()
).decode("utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def require_auth(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency guarding the article endpoints (SDLCAIP1-11).

    Missing header, malformed scheme, or an invalid/expired/bad-signature
    JWT all map to the same 401 response — never raises anything other
    than HTTPException, so a malformed header can't crash the server.
    """
    scheme, token = get_authorization_scheme_param(authorization or "")
    if not authorization or scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


articles_router = APIRouter(dependencies=[Depends(require_auth)])


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    published_at: datetime


class Article(ArticleCreate):
    id: str


class ArticleSummary(BaseModel):
    id: str
    title: str
    published_at: datetime


class ArticleListResponse(BaseModel):
    items: list[ArticleSummary]
    total: int
    total_pages: int
    page: int
    page_size: int


def get_articles_table():
    """Lazily create the DynamoDB table resource so it can be mocked in tests."""
    table_name = os.environ["ARTICLES_TABLE_NAME"]
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def get_s3_client():
    """Lazily create the S3 client so it can be mocked in tests."""
    return boto3.client("s3")


class StaticPageDeletionError(Exception):
    def __init__(self, article_id: str, cause: Exception) -> None:
        self.article_id = article_id
        self.cause = cause
        super().__init__(f"Failed to delete static page for article_id={article_id}: {cause}")


def _delete_static_page(article_id: str) -> None:
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    key = f"articles/{article_id}.html"
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "Failed to delete static page for article_id=%s: %s",
            article_id,
            exc,
        )
        raise StaticPageDeletionError(article_id, exc) from exc


class StaticPageGenerationError(Exception):
    def __init__(self, article_id: str, cause: Exception) -> None:
        self.article_id = article_id
        self.cause = cause
        super().__init__(f"Failed to generate static page for article_id={article_id}: {cause}")


_ARTICLE_PAGE_STYLE = """
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 16px;
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      line-height: 1.6;
      overflow-wrap: break-word;
    }
    .article { max-width: 100%; }
    .article__title { font-size: 1.5rem; margin: 0 0 8px; }
    .article__meta { display: block; color: #666; font-size: 0.875rem; margin-bottom: 16px; }
    .article__content { white-space: pre-wrap; }
    img, pre, table { max-width: 100%; }

    /* 平板 768-1024px */
    @media (min-width: 768px) and (max-width: 1024px) {
      body { padding: 24px; }
      .article__title { font-size: 1.75rem; }
    }

    /* 桌機 >1024px */
    @media (min-width: 1025px) {
      body { padding: 32px; }
      .article { max-width: 800px; margin: 0 auto; }
      .article__title { font-size: 2rem; }
    }
    """


_ARTICLE_DETAIL_PAGE_STYLE = """
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: var(--space-4);
      font-family: var(--font-family-base);
      line-height: 1.6;
      overflow-wrap: break-word;
    }
    .article { max-width: 100%; }
    .article__title { font-size: 1.5rem; margin: 0 0 var(--space-2); color: var(--color-text-primary); text-align: center; }
    .article__meta { display: block; color: var(--color-text-secondary); font-size: 0.875rem; margin-bottom: var(--space-4); text-align: center; }
    .article__content { white-space: pre-wrap; color: var(--color-text-primary); text-align: left; }
    img, pre, table { max-width: 100%; }

    /* 平板 768-1024px */
    @media (min-width: 768px) and (max-width: 1024px) {
      body { padding: var(--space-5); }
      .article__title { font-size: 1.75rem; }
    }

    /* 桌機 >1024px */
    @media (min-width: 1025px) {
      body { padding: var(--space-6); }
      .article { max-width: 800px; margin: 0 auto; }
      .article__title { font-size: 2rem; }
    }
    """


def _generate_and_upload_static_page(article: Article) -> None:
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    key = f"articles/{article.id}.html"
    title = html.escape(article.title)
    content = html.escape(article.content)
    published_at_iso = article.published_at.isoformat()
    published_at_display = article.published_at.strftime("%Y-%m-%d %H:%M")
    body = (
        "<!DOCTYPE html>"
        '<html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>"
        '<link rel="stylesheet" href="/design-tokens.css">'
        f"<style>{_ARTICLE_DETAIL_PAGE_STYLE}</style>"
        "</head>"
        '<body><article class="article">'
        f'<h1 class="article__title">{title}</h1>'
        f'<time class="article__meta" datetime="{published_at_iso}">{published_at_display}</time>'
        f'<div class="article__content">{content}</div>'
        '<a href="/search.html">搜尋文章</a>'
        "</article></body></html>"
    )
    s3 = get_s3_client()
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/html")
    except (BotoCoreError, ClientError) as exc:
        raise StaticPageGenerationError(article.id, exc) from exc


STATIC_PAGE_GENERATION_FAILED_RESPONSE = {
    "error": "STATIC_PAGE_GENERATION_FAILED",
    "message": "Article could not be published: static page upload failed.",
}


def _publish_or_rollback(article: Article, table) -> JSONResponse | None:
    """Upload the static page for `article` and regenerate all homepage
    list pages; on failure of either step, roll back the DynamoDB write by
    deleting the item and return the 502 response the caller should
    return. Returns None on success.

    Used by update_article (SDLCAIP1-24, extended in SDLCAIP1-27 to also
    regenerate the search index, and in SDLCAIP1-28 to also refresh the
    search page); create_article uses the separate
    _publish_article_and_lists_or_rollback."""
    try:
        _generate_and_upload_static_page(article)
        _generate_and_upload_list_pages(table)
        _generate_and_upload_search_index(table)
        _generate_and_upload_search_page()
        _generate_and_upload_design_tokens()
    except StaticPageGenerationError as upload_exc:
        try:
            table.delete_item(Key={"id": article.id})
        except (BotoCoreError, ClientError) as delete_exc:
            logger.error(
                "Failed to roll back DynamoDB item for article_id=%s after static "
                "page upload failure. Upload failure cause: %s. Rollback delete "
                "failure cause: %s.",
                article.id,
                upload_exc.cause,
                delete_exc,
            )
        return JSONResponse(status_code=502, content=STATIC_PAGE_GENERATION_FAILED_RESPONSE)
    return None


LIST_PAGE_SIZE = 10  # 與 GET /articles 現有預設 page_size 一致


def _list_page_key(page: int) -> str:
    """page=1 -> 'index.html'；page>=2 -> 'page/{page}.html'。"""
    if page == 1:
        return "index.html"
    return f"page/{page}.html"


_LIST_PAGE_STYLE = """
    .article-list {
      list-style: none;
      padding: 0;
      margin: 0;
      font-family: var(--font-family-base);
    }
    .article-list__item {
      padding: var(--space-3) 0;
      text-align: center;
    }
    .article-list__link {
      font-size: 1.125rem;
      text-decoration: none;
      color: var(--color-text-primary);
    }
    .article-list__meta {
      display: block;
      color: var(--color-text-secondary);
      font-size: var(--font-size-meta);
      line-height: var(--line-height-meta);
      margin-top: var(--space-1);
    }
    .pagination {
      display: flex;
      gap: var(--space-3);
      align-items: center;
      margin-top: var(--space-5);
    }
    """


def _render_list_page_html(page_items: list[dict], page: int, total_pages: int) -> str:
    """page_items 為 DynamoDB 原始 item dict（含 id/title/published_at 字串）
    的當頁切片，已由呼叫端排序、切好；本函式只負責組 HTML 字串。"""
    items_html = ""
    for item in page_items:
        title = html.escape(item["title"])
        published_at = datetime.fromisoformat(item["published_at"])
        published_at_iso = published_at.isoformat()
        published_at_display = published_at.strftime("%Y-%m-%d %H:%M")
        items_html += (
            '<li class="article-list__item">'
            f'<a class="article-list__link" href="/articles/{item["id"]}.html">{title}</a>'
            f'<time class="article-list__meta" datetime="{published_at_iso}">'
            f"{published_at_display}</time>"
            "</li>"
        )

    nav_html = ""
    if page > 1:
        prev_href = "/" + _list_page_key(page - 1)
        nav_html += f'<a href="{prev_href}">上一頁</a>'
    nav_html += f"<span>第 {page} / {total_pages} 頁</span>"
    if page < total_pages:
        next_href = "/" + _list_page_key(page + 1)
        nav_html += f'<a href="{next_href}">下一頁</a>'

    return (
        "<!DOCTYPE html>"
        '<html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>文章列表 - 第 {page} 頁</title>"
        f"<style>{_ARTICLE_PAGE_STYLE}{_LIST_PAGE_STYLE}</style>"
        '<link rel="stylesheet" href="/design-tokens.css">'
        "</head>"
        "<body>"
        '<a href="/search.html">搜尋文章</a>'
        f'<ul class="article-list">{items_html}</ul>'
        f'<nav class="pagination">{nav_html}</nav>'
        "</body></html>"
    )


def _generate_and_upload_list_pages(table) -> None:
    """對 `table` 做 ConsistentRead=True 的 scan()，依 published_at 由新到舊
    排序，依 LIST_PAGE_SIZE 切頁，對每一頁呼叫 _render_list_page_html 並
    s3.put_object 上傳（key 用 _list_page_key）。任一頁上傳失敗即拋出
    StaticPageGenerationError(f"list-page-{page}", exc)，中止後續頁面上傳。

    total_pages 至少為 1：即使 table 目前沒有任何文章（total == 0），仍會產生並
    上傳第 1 頁（index.html）作為空狀態頁面（page_items 為空、total_pages=1），
    確保 S3 上的列表頁不會停留在刪除前的舊內容。"""
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    s3 = get_s3_client()

    response = table.scan(ConsistentRead=True)
    items = response.get("Items", [])
    items.sort(key=lambda item: item["published_at"], reverse=True)

    total = len(items)
    total_pages = max(1, math.ceil(total / LIST_PAGE_SIZE)) if total else 1

    for page in range(1, total_pages + 1):
        start = (page - 1) * LIST_PAGE_SIZE
        end = start + LIST_PAGE_SIZE
        page_items = items[start:end]
        body = _render_list_page_html(page_items, page, total_pages)
        key = _list_page_key(page)
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/html")
        except (BotoCoreError, ClientError) as exc:
            raise StaticPageGenerationError(f"list-page-{page}", exc) from exc


SEARCH_INDEX_KEY = "search/index.json"


def _build_search_index_entry(item: dict) -> dict:
    """將 DynamoDB 原始 item dict（含 id/title/content/published_at 字串）轉為
    索引項目 {"id", "title", "content", "published_at"}（HUMAN-INPUT SDLCAIP1-25
    核准欄位：content 為全文，不截斷/摘要）。published_at 維持 ISO 字串
    （item 原始儲存格式，不重新格式化），供前端 SDLCAIP1-28 的 vanilla JS 直接
    使用，不需額外的日期解析。"""
    return {
        "id": item["id"],
        "title": item["title"],
        "content": item["content"],
        "published_at": item["published_at"],
    }


def _generate_and_upload_search_index(table) -> None:
    """對 `table` 做 ConsistentRead=True 的 scan()，對每筆 item 呼叫
    _build_search_index_entry，組成 JSON 陣列（json.dumps(..., ensure_ascii=False)
    以正確輸出中文全文，不轉義成 \\uXXXX），以 s3.put_object 上傳至
    SEARCH_INDEX_KEY（ContentType="application/json"）。scan() 回傳空清單時仍
    上傳空陣列 `[]`（不略過上傳——比照 _generate_and_upload_list_pages 對
    total == 0 的既有處理）。上傳失敗即拋出
    StaticPageGenerationError("search-index", exc)（沿用既有例外類別，
    'search-index' 作為 log 訊息的識別字串，不新增例外類別）。"""
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    s3 = get_s3_client()

    response = table.scan(ConsistentRead=True)
    items = response.get("Items", [])
    entries = [_build_search_index_entry(item) for item in items]
    body = json.dumps(entries, ensure_ascii=False)

    try:
        s3.put_object(
            Bucket=bucket, Key=SEARCH_INDEX_KEY, Body=body, ContentType="application/json"
        )
    except (BotoCoreError, ClientError) as exc:
        raise StaticPageGenerationError("search-index", exc) from exc


SEARCH_PAGE_KEY = "search.html"

_SEARCH_PAGE_STYLE = """
    .search-form__input {
      width: 100%;
      padding: var(--space-2) var(--space-3);
      font-size: 1rem;
      box-sizing: border-box;
      margin-bottom: var(--space-4);
    }
    .article-list__item {
      padding: var(--space-3) 0;
      text-align: center;
    }
    .article-list__link {
      color: var(--color-text-primary);
      font-size: 1.125rem;
      text-decoration: none;
    }
    """

_SEARCH_PAGE_SCRIPT = """
(function () {
  var input = document.getElementById("search-input");
  var resultsEl = document.getElementById("search-results");
  var emptyEl = document.getElementById("search-empty");
  var indexData = null;

  fetch("/search/index.json")
    .then(function (res) { return res.json(); })
    .then(function (data) { indexData = data; })
    .catch(function () { indexData = []; });

  input.addEventListener("input", function () {
    var keyword = input.value.trim();
    resultsEl.innerHTML = "";
    emptyEl.hidden = true;

    if (keyword === "") {
      return; // AC7：空搜尋框不顯示任何結果或錯誤
    }

    var lowerKeyword = keyword.toLowerCase();
    var matches = (indexData || []).filter(function (item) {
      return item.title.toLowerCase().indexOf(lowerKeyword) !== -1 ||
             item.content.toLowerCase().indexOf(lowerKeyword) !== -1;
    });

    if (matches.length === 0) {
      emptyEl.hidden = false; // AC5
      return;
    }

    matches.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "article-list__item";
      var a = document.createElement("a");
      a.className = "article-list__link";
      a.href = "/articles/" + item.id + ".html";
      a.textContent = item.title;
      li.appendChild(a);
      resultsEl.appendChild(li);
    });
  });
})();
"""


def _generate_and_upload_search_page() -> None:
    """產生並上傳固定不變的搜尋頁骨架（search.html，S3 bucket 根目錄）。內容
    不依賴任何文章資料——比對邏輯在瀏覽器端讀取 search/index.json 執行
    （SDLCAIP1-26/27），本函式只負責上傳靜態骨架頁本身。上傳失敗即拋出
    StaticPageGenerationError("search-page", exc)（沿用既有例外類別，不新增
    錯誤碼），比照其他靜態頁上傳失敗的既有 rollback/502 處理路徑。"""
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    body = (
        "<!DOCTYPE html>"
        '<html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>搜尋文章</title>"
        f"<style>{_ARTICLE_PAGE_STYLE}{_SEARCH_PAGE_STYLE}</style>"
        '<link rel="stylesheet" href="/design-tokens.css">'
        "</head>"
        "<body>"
        '<form class="search-form" id="search-form" onsubmit="return false;">'
        '<input type="text" id="search-input" class="search-form__input" '
        'placeholder="輸入關鍵字搜尋文章" autocomplete="off">'
        "</form>"
        '<ul class="article-list" id="search-results"></ul>'
        '<p class="search-empty" id="search-empty" hidden>查無符合的文章</p>'
        f"<script>{_SEARCH_PAGE_SCRIPT}</script>"
        "</body></html>"
    )
    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket=bucket, Key=SEARCH_PAGE_KEY, Body=body, ContentType="text/html"
        )
    except (BotoCoreError, ClientError) as exc:
        raise StaticPageGenerationError("search-page", exc) from exc


DESIGN_TOKENS_KEY = "design-tokens.css"

_DESIGN_TOKENS_PATH = os.path.join(os.path.dirname(__file__), "static", "design-tokens.css")


def _generate_and_upload_design_tokens() -> None:
    """讀取 src/cms_aipilot/static/design-tokens.css（SDLCAIP1-30，內容比照
    docs/design-system.md 第 1-5 節，固定不依賴文章資料）並上傳至 S3 bucket
    根目錄 DESIGN_TOKENS_KEY（ContentType="text/css"）。讀檔或上傳任一步驟
    失敗皆拋出 StaticPageGenerationError("design-tokens", exc)（沿用既有例外
    類別，不新增錯誤碼/例外類別），比照 _generate_and_upload_search_page 的
    既有模式。"""
    bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
    try:
        with open(_DESIGN_TOKENS_PATH, encoding="utf-8") as f:
            body = f.read()
    except OSError as exc:
        raise StaticPageGenerationError("design-tokens", exc) from exc

    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket=bucket, Key=DESIGN_TOKENS_KEY, Body=body, ContentType="text/css"
        )
    except (BotoCoreError, ClientError) as exc:
        raise StaticPageGenerationError("design-tokens", exc) from exc


def _publish_article_and_lists_or_rollback(article: Article, table) -> JSONResponse | None:
    """僅供 create_article 使用（不影響 update_article 既有的
    _publish_or_rollback）。依序呼叫 _generate_and_upload_static_page(article)、
    _generate_and_upload_list_pages(table)、
    _generate_and_upload_search_index(table)、
    _generate_and_upload_search_page() 與
    _generate_and_upload_design_tokens()，任一方拋出
    StaticPageGenerationError 即中止，執行既有 rollback，回傳 502
    JSONResponse；全部成功回傳 None。"""
    try:
        _generate_and_upload_static_page(article)
        _generate_and_upload_list_pages(table)
        _generate_and_upload_search_index(table)
        _generate_and_upload_search_page()
        _generate_and_upload_design_tokens()
    except StaticPageGenerationError as upload_exc:
        try:
            table.delete_item(Key={"id": article.id})
        except (BotoCoreError, ClientError) as delete_exc:
            logger.error(
                "Failed to roll back DynamoDB item for article_id=%s after static "
                "page upload failure. Upload failure cause: %s. Rollback delete "
                "failure cause: %s.",
                article.id,
                upload_exc.cause,
                delete_exc,
            )
        return JSONResponse(status_code=502, content=STATIC_PAGE_GENERATION_FAILED_RESPONSE)
    return None


@articles_router.post("/articles", status_code=201, response_model=None)
def create_article(article: ArticleCreate) -> Article | JSONResponse:
    created = Article(id=str(uuid.uuid4()), **article.model_dump())
    table = get_articles_table()
    table.put_item(
        Item={
            "id": created.id,
            "title": created.title,
            "content": created.content,
            "published_at": created.published_at.isoformat(),
        }
    )
    rollback_response = _publish_article_and_lists_or_rollback(created, table)
    if rollback_response is not None:
        return rollback_response
    return created


@articles_router.get("/articles")
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> ArticleListResponse:
    table = get_articles_table()
    response = table.scan()
    items = response.get("Items", [])
    items.sort(key=lambda item: item["published_at"], reverse=True)

    total = len(items)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return ArticleListResponse(
        items=[ArticleSummary(**item) for item in page_items],
        total=total,
        total_pages=total_pages,
        page=page,
        page_size=page_size,
    )


@articles_router.get("/articles/{article_id}")
def get_article(article_id: str) -> Article:
    table = get_articles_table()
    response = table.get_item(Key={"id": article_id})
    item = response.get("Item")
    if item is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return Article(**item)


@articles_router.put("/articles/{article_id}", response_model=None)
def update_article(article_id: str, article: ArticleCreate) -> Article | JSONResponse:
    table = get_articles_table()
    existing = table.get_item(Key={"id": article_id})
    if existing.get("Item") is None:
        raise HTTPException(status_code=404, detail="Article not found")

    updated = Article(id=article_id, **article.model_dump())
    table.put_item(
        Item={
            "id": updated.id,
            "title": updated.title,
            "content": updated.content,
            "published_at": updated.published_at.isoformat(),
        }
    )
    rollback_response = _publish_or_rollback(updated, table)
    if rollback_response is not None:
        return rollback_response
    return updated


@articles_router.delete("/articles/{article_id}", status_code=204)
def delete_article(article_id: str) -> Response:
    table = get_articles_table()
    existing = table.get_item(Key={"id": article_id})
    if existing.get("Item") is None:
        raise HTTPException(status_code=404, detail="Article not found")

    table.delete_item(Key={"id": article_id})

    try:
        _delete_static_page(article_id)
    except StaticPageDeletionError:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "STATIC_PAGE_DELETION_FAILED",
                "detail": "Article deleted but its static page could not be removed from S3.",
                "article_id": article_id,
            },
        )

    try:
        _generate_and_upload_list_pages(table)
    except StaticPageGenerationError:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "STATIC_LIST_PAGE_REGENERATION_FAILED",
                "detail": (
                    "Article deleted but the homepage list pages could not be "
                    "regenerated."
                ),
                "article_id": article_id,
            },
        )

    try:
        _generate_and_upload_search_index(table)
    except StaticPageGenerationError:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "STATIC_SEARCH_INDEX_REGENERATION_FAILED",
                "detail": "Article deleted but the search index could not be regenerated.",
                "article_id": article_id,
            },
        )

    try:
        _generate_and_upload_search_page()
    except StaticPageGenerationError:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "STATIC_SEARCH_PAGE_REGENERATION_FAILED",
                "detail": "Article deleted but the search page could not be regenerated.",
                "article_id": article_id,
            },
        )

    try:
        _generate_and_upload_design_tokens()
    except StaticPageGenerationError:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "STATIC_DESIGN_TOKENS_REGENERATION_FAILED",
                "detail": (
                    "Article deleted but the design tokens stylesheet could not be "
                    "regenerated."
                ),
                "article_id": article_id,
            },
        )
    return Response(status_code=204)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_auth_table():
    """Lazily create the DynamoDB table resource so it can be mocked in tests."""
    table_name = os.environ["AUTH_TABLE_NAME"]
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def _get_auth_state(table) -> dict:
    response = table.get_item(Key={"id": AUTH_STATE_ID})
    item = response.get("Item")
    if item is None:
        return {"failed_attempts": 0, "locked_until": 0}
    return {
        "failed_attempts": int(item.get("failed_attempts", 0)),
        "locked_until": int(item.get("locked_until", 0)),
    }


@app.post("/login")
def login(credentials: LoginRequest) -> TokenResponse:
    table = get_auth_table()
    state = _get_auth_state(table)
    now = int(time.time())

    if state["locked_until"] > now:
        retry_after = max(0, state["locked_until"] - now)
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Account locked. Try again in {retry_after} seconds.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    admin_username = get_admin_username()
    admin_password_hash = get_admin_password_hash()

    username_matches = credentials.username == admin_username
    # Always run bcrypt.checkpw (against the real hash if the username
    # matches, otherwise against a fixed dummy hash) so a wrong username and
    # a wrong password take the same amount of time — avoids leaking valid
    # usernames via a timing side-channel.
    password_hash_to_check = admin_password_hash if username_matches else _DUMMY_PASSWORD_HASH
    password_matches = bcrypt.checkpw(
        credentials.password.encode("utf-8"), password_hash_to_check.encode("utf-8")
    )
    valid = username_matches and password_matches

    if not valid:
        # Atomic server-side increment (ADD) instead of read-then-write, so
        # concurrent failed attempts can't race and undercount.
        result = table.update_item(
            Key={"id": AUTH_STATE_ID},
            UpdateExpression="ADD failed_attempts :incr",
            ExpressionAttributeValues={":incr": 1},
            ReturnValues="UPDATED_NEW",
        )
        failed_attempts = int(result["Attributes"]["failed_attempts"])
        if failed_attempts >= LOCKOUT_THRESHOLD:
            table.update_item(
                Key={"id": AUTH_STATE_ID},
                UpdateExpression="SET locked_until = :locked_until",
                ExpressionAttributeValues={":locked_until": now + LOCKOUT_DURATION_SECONDS},
            )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    table.update_item(
        Key={"id": AUTH_STATE_ID},
        UpdateExpression="SET failed_attempts = :zero, locked_until = :zero",
        ExpressionAttributeValues={":zero": 0},
    )
    access_token = create_access_token(subject=admin_username)
    return TokenResponse(access_token=access_token, token_type="bearer")


app.include_router(articles_router)
