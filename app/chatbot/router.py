from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.chatbot.config import chatbot_settings
from app.chatbot.db import get_chatbot_db, get_session_factory
from app.chatbot.rate_limit import limiter
from app.chatbot.rag.providers import ProviderError, QdrantStore
from app.chatbot.service import (
    add_feedback,
    get_history,
    get_or_create_session,
    stream_chat,
)
from app.chatbot.rag.ingest import run_ingestion
from app.chatbot.schemas import (
    ChatRequest,
    FeedbackOut,
    FeedbackRequest,
    HealthOut,
    HistoryOut,
    IngestOut,
    IngestRequest,
    SessionOut,
    SessionRequest,
)
from app.core.dependencies import get_cart_token, get_current_admin, get_optional_user
from app.core.security import generate_cart_token
from app.models import Admin, User
from app.utils.cookies import set_cart_cookie

logger = logging.getLogger("app.chatbot.router")

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])


def _support_email() -> str:
    try:
        from app.database.connection import SessionLocal
        from app.repositories.catalog import CatalogRepository

        db = SessionLocal()
        try:
            return (
                CatalogRepository(db).settings_map().get("support_email")
                or "smith14580@gmail.com"
            )
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return "smith14580@gmail.com"


@router.post("/session", response_model=SessionOut)
@limiter.limit(chatbot_settings.session_rate_limit)
async def create_session(
    request: Request,
    payload: SessionRequest,
    user: User | None = Depends(get_optional_user),
    chat_db: AsyncSession = Depends(get_chatbot_db),
) -> SessionOut:
    session = await get_or_create_session(
        chat_db, requested_id=payload.session_id, user_id=user.id if user else None
    )
    return SessionOut(
        session_id=session.id,
        authenticated=user is not None,
        user_id=user.id if user else None,
    )


@router.post("/chat")
@limiter.limit(chatbot_settings.chat_rate_limit)
async def chat(
    request: Request,
    payload: ChatRequest,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    chat_db: AsyncSession = Depends(get_chatbot_db),
) -> StreamingResponse:
    if len(payload.message) > chatbot_settings.max_message_chars:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Message is too long.",
        )

    new_cart_token: str | None = None
    if user is None and not cart_token:
        new_cart_token = generate_cart_token()
        cart_token = new_cart_token

    support_email = await run_in_threadpool(_support_email)
    generator = stream_chat(
        chat_db,
        session_id=payload.session_id,
        message=payload.message,
        user_id=user.id if user else None,
        cart_token=cart_token,
        support_email=support_email,
    )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if new_cart_token:
        temporary = Response()
        set_cart_cookie(temporary, new_cart_token)
        cookie_header = temporary.headers.get("set-cookie")
        if cookie_header:
            headers["set-cookie"] = cookie_header

    return StreamingResponse(generator, media_type="text/event-stream", headers=headers)


@router.get("/history/{session_id}", response_model=HistoryOut)
async def history(
    session_id: str,
    user: User | None = Depends(get_optional_user),
    chat_db: AsyncSession = Depends(get_chatbot_db),
) -> HistoryOut:
    data = await get_history(
        chat_db, session_id=session_id, user_id=user.id if user else None
    )
    return HistoryOut(**data)


@router.post("/ingest", response_model=IngestOut)
@limiter.limit(chatbot_settings.ingest_rate_limit)
async def ingest(
    request: Request,
    payload: IngestRequest,
    admin: Admin = Depends(get_current_admin),
    chat_db: AsyncSession = Depends(get_chatbot_db),
) -> IngestOut:
    _ = (admin, chat_db)
    try:
        result = await run_ingestion(
            rebuild=payload.rebuild,
            include_database=payload.include_database,
            include_site_content=payload.include_site_content,
        )
    except ProviderError as exc:
        logger.warning("Ingestion provider error: %s", str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A content provider rejected the ingestion request.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ingestion failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ingestion failed. Check the backend logs.",
        ) from exc

    return IngestOut(status="ok", **result)


@router.post("/feedback", response_model=FeedbackOut)
async def feedback(
    payload: FeedbackRequest,
    user: User | None = Depends(get_optional_user),
    chat_db: AsyncSession = Depends(get_chatbot_db),
) -> FeedbackOut:
    await add_feedback(
        chat_db,
        session_id=payload.session_id,
        user_id=user.id if user else None,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    return FeedbackOut()


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    database = "not_configured"
    factory = get_session_factory()
    if factory is not None:
        try:
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            database = "ok"
        except Exception:  # noqa: BLE001
            database = "error"

    qdrant = "not_configured"
    collection = chatbot_settings.qdrant_collection
    if chatbot_settings.qdrant_configured:
        try:
            qdrant = "ok" if await run_in_threadpool(QdrantStore().health) else "missing_collection"
        except Exception:  # noqa: BLE001
            qdrant = "error"

    cohere = "configured" if chatbot_settings.cohere_configured else "missing"
    openrouter = "configured" if chatbot_settings.openrouter_configured else "missing"
    overall = "ok"
    if database != "ok" or qdrant not in {"ok"} or cohere != "configured" or openrouter != "configured":
        overall = "degraded"

    return HealthOut(
        status=overall,
        database=database,
        qdrant=qdrant,
        collection=collection,
        cohere=cohere,
        openrouter=openrouter,
    )
