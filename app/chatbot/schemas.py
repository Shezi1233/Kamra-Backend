from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.chatbot.config import chatbot_settings


class SessionRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)


class SessionOut(BaseModel):
    session_id: str
    authenticated: bool
    user_id: int | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=chatbot_settings.max_message_chars)

    @field_validator("message")
    @classmethod
    def _clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")
        if len(cleaned) > chatbot_settings.max_message_chars:
            raise ValueError("Message is too long.")
        return cleaned


class ProductOut(BaseModel):
    id: int
    title: str
    slug: str
    short_description: str | None = None
    price: str | None = None
    price_label: str
    delivery_estimate: str | None = None
    image: str | None = None
    category_name: str | None = None
    category_slug: str | None = None


class HistoryMessageOut(BaseModel):
    id: int
    role: str
    content: str
    products: list[ProductOut] = Field(default_factory=list)
    created_at: datetime | None = None


class HistoryOut(BaseModel):
    session_id: str
    messages: list[HistoryMessageOut]


class IngestRequest(BaseModel):
    rebuild: bool = False
    include_database: bool = True
    include_site_content: bool = True


class IngestOut(BaseModel):
    status: str
    collection: str
    documents: int
    chunks: int
    points: int
    duration_ms: int


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message_id: int | None = None
    rating: str = Field(pattern="^(up|down)$")
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    status: str = "ok"


class HealthOut(BaseModel):
    status: str
    database: str
    qdrant: str
    collection: str
    cohere: str
    openrouter: str
