from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.chatbot.agent.llm import build_system_prompt, run_agent_stream, to_llm_messages
from app.chatbot.agent.tools import ToolContext
from app.chatbot.config import chatbot_settings
from app.chatbot.models import ChatMessage, ChatSession, PendingAction
from app.chatbot.rag.retriever import retrieve_context

logger = logging.getLogger("app.chatbot.service")


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def _session_owned_by(session: ChatSession, user_id: int | None) -> bool:
    if session.user_id is None:
        return True
    return user_id is not None and int(session.user_id) == int(user_id)


async def get_or_create_session(
    chat_db: AsyncSession, *, requested_id: str | None, user_id: int | None
) -> ChatSession:
    if requested_id:
        session = await chat_db.get(ChatSession, requested_id)
        if session is not None and _session_owned_by(session, user_id):
            return session
    session = ChatSession(id=uuid.uuid4().hex, user_id=user_id)
    chat_db.add(session)
    await chat_db.commit()
    await chat_db.refresh(session)
    return session


async def load_session(
    chat_db: AsyncSession, session_id: str, user_id: int | None
) -> ChatSession:
    session = await chat_db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    if not _session_owned_by(session, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This chat session belongs to another account.",
        )
    return session


async def get_history(
    chat_db: AsyncSession, *, session_id: str, user_id: int | None
) -> dict[str, Any]:
    session = await load_session(chat_db, session_id, user_id)
    rows = (
        await chat_db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.visible == 1)
            .order_by(ChatMessage.id.asc())
            .limit(200)
        )
    ).all()
    messages = []
    for row in rows:
        if row.role not in {"user", "assistant"} or not (row.content or "").strip():
            continue
        payload = row.payload or {}
        messages.append(
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "products": payload.get("products", []) if isinstance(payload, dict) else [],
                "created_at": row.created_at,
            }
        )
    return {"session_id": session.id, "messages": messages}


async def _load_history_rows(
    chat_db: AsyncSession, session_id: str
) -> list[ChatMessage]:
    rows = (
        await chat_db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(chatbot_settings.history_limit)
        )
    ).all()
    return list(reversed(rows))


async def _pending_actions(
    chat_db: AsyncSession, session_id: str
) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    rows = (
        await chat_db.scalars(
            select(PendingAction)
            .where(
                PendingAction.session_id == session_id,
                PendingAction.consumed == 0,
                PendingAction.expires_at > now,
            )
            .order_by(PendingAction.created_at.desc())
        )
    ).all()
    return [
        {
            "intent": action.intent,
            "service_id": action.service_id,
            "item_id": action.item_id,
            "quantity": action.quantity,
        }
        for action in rows
    ]


async def stream_chat(
    chat_db: AsyncSession,
    *,
    session_id: str,
    message: str,
    user_id: int | None,
    cart_token: str | None,
    support_email: str = "smith14580@gmail.com",
) -> AsyncIterator[str]:
    session = await load_session(chat_db, session_id, user_id)

    history_rows = await _load_history_rows(chat_db, session.id)

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message,
        visible=1,
    )
    chat_db.add(user_message)
    if not session.title:
        session.title = message[:120]
    await chat_db.commit()

    context = await run_in_threadpool(retrieve_context, message)
    pending = await _pending_actions(chat_db, session.id)
    system_prompt = build_system_prompt(
        context=context, pending_actions=pending, support_email=support_email
    )

    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(to_llm_messages(history_rows))
    llm_messages.append({"role": "user", "content": message})

    tool_context = ToolContext(
        session_id=session.id,
        user_id=user_id,
        cart_token=cart_token,
        latest_user_message=message,
    )
    record: list[dict[str, Any]] = []
    products: list[dict[str, Any]] = []
    terminal_event: dict[str, Any] | None = None

    yield sse({"type": "start", "session_id": session.id})

    try:
        async for event in run_agent_stream(
            messages=llm_messages,
            context=tool_context,
            chat_db=chat_db,
            record=record,
        ):
            if event.get("type") == "products":
                for product in event.get("products") or []:
                    if product not in products:
                        products.append(product)
            if event.get("type") == "done":
                terminal_event = event
                break
            yield sse(event)
            if event.get("type") == "error":
                terminal_event = event
                break
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chat stream failed: %s", type(exc).__name__)
        terminal_event = {
            "type": "error",
            "message": "Something went wrong while answering. Please try again.",
        }

    try:
        await _persist_turn(chat_db, session, record, products)
    except Exception:  # noqa: BLE001
        logger.warning("Could not persist chatbot turn", exc_info=True)

    if terminal_event is None:
        terminal_event = {"type": "done"}
    if terminal_event.get("type") != "done":
        # Errors were already streamed in the loop above.
        return
    yield sse(terminal_event)


async def _persist_turn(
    chat_db: AsyncSession,
    session: ChatSession,
    record: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> None:
    if not record:
        session.updated_at = datetime.utcnow()
        await chat_db.commit()
        return

    last_visible_index = -1
    for index, item in enumerate(record):
        if item.get("role") == "assistant" and not item.get("tool_calls"):
            if str(item.get("content") or "").strip():
                last_visible_index = index

    for index, item in enumerate(record):
        role = str(item.get("role") or "")
        content = str(item.get("content") or "")
        if role == "assistant":
            tool_calls = item.get("tool_calls")
            visible = 1 if (not tool_calls and content.strip()) else 0
            payload = (
                {"products": products}
                if visible and index == last_visible_index and products
                else None
            )
            chat_db.add(
                ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    payload=payload,
                    visible=visible,
                )
            )
        elif role == "tool":
            chat_db.add(
                ChatMessage(
                    session_id=session.id,
                    role="tool",
                    content=content,
                    tool_call_id=item.get("tool_call_id"),
                    name=item.get("name"),
                    visible=0,
                )
            )
    session.updated_at = datetime.utcnow()
    await chat_db.commit()


async def add_feedback(
    chat_db: AsyncSession,
    *,
    session_id: str,
    user_id: int | None,
    message_id: int | None,
    rating: str,
    comment: str | None,
) -> None:
    from app.chatbot.models import ChatFeedback

    await load_session(chat_db, session_id, user_id)
    chat_db.add(
        ChatFeedback(
            session_id=session_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
        )
    )
    await chat_db.commit()
