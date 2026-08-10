import os
import uuid
from datetime import datetime

import boto3
from fastapi import FastAPI, HTTPException
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
