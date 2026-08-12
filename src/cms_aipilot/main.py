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


@articles_router.post("/articles", status_code=201)
def create_article(article: ArticleCreate) -> Article:
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


@articles_router.put("/articles/{article_id}")
def update_article(article_id: str, article: ArticleCreate) -> Article:
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
