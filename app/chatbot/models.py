from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.chatbot.db import ChatbotBase


def _uuid_hex() -> str:
    return uuid.uuid4().hex


class ChatSession(ChatbotBase):
    __tablename__ = "chatbot_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid_hex)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    actions: Mapped[list["PendingAction"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(ChatbotBase):
    __tablename__ = "chatbot_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chatbot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    visible: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_chatbot_messages_session_id_id", "session_id", "id"),)


class PendingAction(ChatbotBase):
    __tablename__ = "chatbot_pending_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid_hex)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chatbot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent: Mapped[str] = mapped_column(String(20), nullable=False)
    service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    session: Mapped[ChatSession] = relationship(back_populates="actions")


class IngestionLog(ChatbotBase):
    __tablename__ = "chatbot_ingestion_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    collection: Mapped[str] = mapped_column(String(120), nullable=False)
    documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class ChatFeedback(ChatbotBase):
    __tablename__ = "chatbot_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chatbot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chatbot_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
