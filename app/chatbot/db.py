from __future__ import annotations

import asyncio
import logging
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase

from app.chatbot.config import chatbot_settings

logger = logging.getLogger("app.chatbot.db")


class ChatbotBase(DeclarativeBase):
    """Declarative base for chatbot-only tables."""


@lru_cache
def get_engine() -> AsyncEngine | None:
    if not chatbot_settings.database_configured:
        return None
    try:
        return create_async_engine(
            chatbot_settings.chatbot_sqlalchemy_url,
            pool_pre_ping=True,
            pool_size=chatbot_settings.db_pool_size,
            max_overflow=chatbot_settings.db_max_overflow,
            pool_recycle=chatbot_settings.db_pool_recycle,
            connect_args={"prepare_threshold": None},
            future=True,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Chatbot database engine could not be created.", exc_info=True)
        return None


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
    try:
        async with factory() as session:
            yield session
    except DBAPIError as exc:
        logger.warning("Chatbot database unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chatbot database is unavailable.",
        ) from exc


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
