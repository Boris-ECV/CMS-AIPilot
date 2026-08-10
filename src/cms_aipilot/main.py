import math
import os
import uuid
from datetime import datetime

import boto3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="CMS AI Pilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


@app.post("/articles", status_code=201)
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


@app.get("/articles")
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


@app.get("/articles/{article_id}")
def get_article(article_id: str) -> Article:
    table = get_articles_table()
    response = table.get_item(Key={"id": article_id})
    item = response.get("Item")
    if item is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return Article(**item)


@app.put("/articles/{article_id}")
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


@app.delete("/articles/{article_id}", status_code=204)
def delete_article(article_id: str) -> None:
    table = get_articles_table()
    existing = table.get_item(Key={"id": article_id})
    if existing.get("Item") is None:
        raise HTTPException(status_code=404, detail="Article not found")

    table.delete_item(Key={"id": article_id})
