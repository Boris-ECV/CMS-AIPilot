import os
import uuid
from datetime import datetime

import boto3
from fastapi import FastAPI
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
