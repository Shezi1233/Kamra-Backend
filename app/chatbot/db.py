from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from functools import lru_cache

# psycopg's async driver cannot use Windows' default ProactorEventLoop.
if sys.platform == "win32":  # pragma: no cover - platform specific
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001
        pass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.chatbot.config import chatbot_settings


class ChatbotBase(DeclarativeBase):
    """Declarative base for chatbot-only tables."""


@lru_cache
def get_engine() -> AsyncEngine | None:
    if not chatbot_settings.database_configured:
        return None
    return create_async_engine(
        chatbot_settings.chatbot_sqlalchemy_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    engine = get_engine()
    if engine is None:
        return None
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_chatbot_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chatbot database is not configured.",
        )
    async with factory() as session:
        yield session


async def init_chatbot_db() -> bool:
    """Create chatbot tables. Safe to run repeatedly."""

    engine = get_engine()
    if engine is None:
        return False

    # Import models so they are registered on the metadata before create_all.
    from app.chatbot import models as _models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(ChatbotBase.metadata.create_all)
    return True


async def dispose_chatbot_db() -> None:
    engine = get_engine()
    if engine is not None:
        await engine.dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
