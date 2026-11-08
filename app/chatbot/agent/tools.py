from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.chatbot.config import chatbot_settings
from app.chatbot.models import PendingAction

logger = logging.getLogger("app.chatbot.tools")


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the website's services/products by keyword. Use this for "
                "recommendations or when the visitor asks what is available, what a "
                "service includes, or which service fits their need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords such as 'e-commerce', 'school system', 'SEO'.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Get full details (description, price, delivery estimate, features) for "
                "one service/product by numeric id or slug."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "integer", "minimum": 1},
                    "slug": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": "Show the current visitor's cart contents and subtotal.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Add a service/product to the visitor's cart. The server requires "
                "confirmation: the first call returns status='confirmation_required' "
                "and does NOT add anything. Ask the visitor to confirm. Only call this "
                "tool again (same service_id/quantity) after the visitor explicitly "
                "confirms."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "integer", "minimum": 1},
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 99,
                        "default": 1,
                    },
                },
                "required": ["service_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": (
                "Remove a cart line by item_id. The server requires confirmation: the "
                "first call returns status='confirmation_required' and does NOT remove "
                "anything. Ask the visitor to confirm, then call again after they confirm."
            ),
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "minimum": 1}},
                "required": ["item_id"],
            },
        },
    },
]


_AFFIRMATIVE_EXACT = {
    "yes",
    "yeah",
    "yep",
    "ok",
    "okay",
    "sure",
    "confirm",
    "confirmed",
    "please do",
    "go ahead",
    "do it",
    "add it",
    "add it please",
    "yes please",
    "yes please add",
    "yes add it",
    "yes add to cart",
    "haan",
    "han",
    "ha",
    "ji",
    "ji haan",
    "haan ji",
    "bilkul",
    "bilkul theek",
    "theek hai",
    "thik hai",
    "theek",
    "thik",
    "kardo",
    "kar do",
    "krdo",
    "add kar do",
    "add kardo",
    "cart me add kar do",
    "cart me daal do",
    "daal do",
    "hata do",
    "remove kar do",
    "remove kardo",
}
_AFFIRMATIVE_START = re.compile(
    r"^(yes|yeah|yep|ok|okay|sure|confirm|confirmed|haan|han|ha|ji|bilkul|theek|thik)\b",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"\b(no|nahi|nah|don't|dont|do not|stop|cancel|wrong|galat)\b", re.IGNORECASE
)
_INJECTION = re.compile(
    r"(ignore|system|prompt|instruction|password|api[_ -]?key|secret|token|developer)",
    re.IGNORECASE,
)


def normalize_confirmation(text: str) -> str:
    cleaned = re.sub(r"[^\w\s']", " ", (text or "").lower())
    return " ".join(cleaned.split())


def is_affirmative(text: str) -> bool:
    cleaned = normalize_confirmation(text)
    if not cleaned or len(cleaned) > 48:
        return False
    if _NEGATIVE.search(cleaned) or _INJECTION.search(cleaned):
        return False
    if cleaned in _AFFIRMATIVE_EXACT:
        return True
    return bool(_AFFIRMATIVE_START.match(cleaned))


@dataclass
class ToolContext:
    session_id: str
    user_id: int | None
    cart_token: str | None
    latest_user_message: str
    new_cart_token: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


def _price_label(price: Decimal | None) -> str:
    if price is None:
        return "Request a Quote"
    try:
        return f"Rs {float(price):,.0f}"
    except (TypeError, ValueError):
        return str(price)


def _product_payload(service: Any) -> dict[str, Any]:
    category = getattr(service, "category", None)
    category_name = getattr(service, "category_name", None) or (
        category.name if category is not None else None
    )
    category_slug = getattr(service, "category_slug", None) or (
        category.slug if category is not None else None
    )
    price = getattr(service, "price", None)
    return {
        "id": int(getattr(service, "id")),
        "title": getattr(service, "title", ""),
        "slug": getattr(service, "slug", ""),
        "short_description": getattr(service, "short_description", None),
        "price": str(price) if price is not None else None,
        "price_label": _price_label(price if isinstance(price, Decimal) else None),
        "delivery_estimate": getattr(service, "delivery_estimate", None),
        "image": getattr(service, "image", None),
        "category_name": category_name,
        "category_slug": category_slug,
    }


def _cart_payload(cart: Any) -> dict[str, Any]:
    lines = []
    for line in getattr(cart, "lines", []) or []:
        item = _product_payload(line)
        item["quantity"] = int(getattr(line, "quantity", 1))
        item["item_id"] = int(getattr(line, "item_id", 0))
        lines.append(item)
    subtotal = getattr(cart, "subtotal", 0)
    try:
        subtotal_decimal = Decimal(str(subtotal))
    except Exception:  # noqa: BLE001
        subtotal_decimal = Decimal("0")
    has_quote = bool(getattr(cart, "has_quote", False))
    if has_quote and subtotal_decimal == 0:
        subtotal_label = "Quote required for one or more items"
    elif has_quote:
        subtotal_label = f"{_price_label(subtotal_decimal)} + quote items"
    else:
        subtotal_label = _price_label(subtotal_decimal)
    return {
        "lines": lines,
        "subtotal": str(subtotal),
        "subtotal_label": subtotal_label,
        "item_count": int(getattr(cart, "item_count", 0) or 0),
        "has_quote": has_quote,
        "cart_token": getattr(cart, "cart_token", None),
    }


def _load_cart_user(db: Any, user_id: int | None) -> Any:
    if not user_id:
        return None
    from app.models import User

    user = db.get(User, int(user_id))
    if user is None or user.is_active != 1:
        return None
    return user


def _tool_search_products(db: Any, query: str, limit: int) -> dict[str, Any]:
    from app.services.catalog_service import CatalogService

    limit = max(1, min(int(limit or 5), 10))
    service = CatalogService(db)
    results = []
    if query.strip():
        results = service.list_services(
            active_only=True, q=query.strip(), sort="featured", limit=limit
        )
        if not results:
            seen: set[int] = set()
            for word in [w for w in re.split(r"\W+", query) if len(w) >= 3][:4]:
                for item in service.list_services(
                    active_only=True, q=word, sort="featured", limit=limit
                ):
                    if item.id in seen:
                        continue
                    seen.add(item.id)
                    results.append(item)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
    if not results:
        results = service.list_services(active_only=True, sort="featured", limit=limit)

    products = [_product_payload(item) for item in results]
    return {"status": "ok", "count": len(products), "products": products}


def _tool_get_product_details(
    db: Any, service_id: int | None, slug: str | None
) -> dict[str, Any]:
    from app.services.catalog_service import CatalogService

    service = CatalogService(db)
    try:
        if service_id:
            item = service.get_service(str(int(service_id)))
        elif slug:
            item = service.get_service(str(slug))
        else:
            return {"status": "error", "message": "Provide service_id or slug."}
    except HTTPException:
        return {"status": "not_found", "message": "That service was not found."}

    product = _product_payload(item)
    product["description"] = getattr(item, "description", None)
    product["features"] = getattr(item, "features", None)
    product["technologies"] = getattr(item, "technologies", None)
    return {"status": "ok", "product": product}


def _tool_view_cart(db: Any, user: Any, cart_token: str | None) -> dict[str, Any]:
    from app.services.cart_service import CartService

    cart = CartService(db).summary(user, cart_token)
    return {"status": "ok", "cart": _cart_payload(cart)}


def _tool_add_to_cart(
    db: Any, user: Any, cart_token: str | None, service_id: int, quantity: int
) -> dict[str, Any]:
    from app.services.cart_service import CartService
    from app.services.catalog_service import CatalogService

    try:
        service = CatalogService(db).get_service(str(int(service_id)))
    except HTTPException:
        return {"status": "not_found", "message": "That service was not found."}
    if getattr(service, "is_active", 1) != 1:
        return {"status": "not_found", "message": "That service is not available."}
    cart = CartService(db).add(user, cart_token, int(service_id), max(1, min(int(quantity), 99)))
    return {
        "status": "added",
        "product": _product_payload(service),
        "cart": _cart_payload(cart),
    }


def _tool_remove_from_cart(
    db: Any, user: Any, cart_token: str | None, item_id: int
) -> dict[str, Any]:
    from app.services.cart_service import CartService

    service = CartService(db)
    summary = service.summary(user, cart_token)
    target = next(
        (line for line in summary.lines if int(line.item_id) == int(item_id)), None
    )
    if target is None:
        return {"status": "not_found", "message": "That cart item was not found."}
    removed = {
        "item_id": int(target.item_id),
        "title": target.title,
        "quantity": int(target.quantity),
    }
    cart = service.remove(user, cart_token, int(item_id))
    return {
        "status": "removed",
        "removed": removed,
        "cart": _cart_payload(cart),
    }


async def _get_pending_action(chat_db: AsyncSession, session_id: str) -> PendingAction | None:
    now = datetime.utcnow()
    return await chat_db.scalar(
        select(PendingAction)
        .where(
            PendingAction.session_id == session_id,
            PendingAction.consumed == 0,
            PendingAction.expires_at > now,
        )
        .order_by(PendingAction.created_at.desc())
        .limit(1)
    )


async def _replace_pending_action(
    chat_db: AsyncSession,
    context: ToolContext,
    *,
    intent: str,
    service_id: int | None = None,
    item_id: int | None = None,
    quantity: int = 1,
) -> PendingAction:
    now = datetime.utcnow()
    existing = await chat_db.scalars(
        select(PendingAction).where(
            PendingAction.session_id == context.session_id,
            PendingAction.consumed == 0,
        )
    )
    for action in existing.all():
        action.consumed = 1
    action = PendingAction(
        session_id=context.session_id,
        intent=intent,
        service_id=service_id,
        item_id=item_id,
        quantity=quantity,
        created_at=now,
        expires_at=now + timedelta(seconds=chatbot_settings.pending_action_ttl_seconds),
        consumed=0,
    )
    chat_db.add(action)
    await chat_db.flush()
    return action


async def _consume_pending_action(chat_db: AsyncSession, action: PendingAction) -> None:
    action.consumed = 1
    await chat_db.flush()


async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    context: ToolContext,
    chat_db: AsyncSession,
) -> dict[str, Any]:
    """Execute one tool call and return a JSON-serialisable result."""

    if name == "search_products":
        query = str(arguments.get("query") or "")
        limit = int(arguments.get("limit") or 5)
        result = await run_in_threadpool(
            lambda: _exec_search(query, limit)
        )
        products = result.get("products") or []
        if products:
            context.events.append({"type": "products", "products": products})
        return result

    if name == "get_product_details":
        service_id = arguments.get("service_id")
        slug = arguments.get("slug")
        result = await run_in_threadpool(
            lambda: _exec_details(service_id, slug)
        )
        if result.get("status") == "ok":
            context.events.append(
                {"type": "products", "products": [result["product"]]}
            )
        return result

    if name == "view_cart":
        result = await run_in_threadpool(lambda: _exec_view_cart(context))
        return result

    if name == "add_to_cart":
        try:
            service_id = int(arguments.get("service_id"))
            quantity = max(1, min(int(arguments.get("quantity") or 1), 99))
        except (TypeError, ValueError):
            return {"status": "error", "message": "service_id must be a number."}
        pending = await _get_pending_action(chat_db, context.session_id)
        confirmed = (
            is_affirmative(context.latest_user_message)
            and pending is not None
            and pending.intent == "add"
            and pending.service_id == service_id
        )
        if not confirmed:
            try:
                details = await run_in_threadpool(
                    lambda: _exec_details(service_id, None)
                )
            except HTTPException:
                return {"status": "not_found", "message": "That service was not found."}
            if details.get("status") != "ok":
                return details
            await _replace_pending_action(
                chat_db,
                context,
                intent="add",
                service_id=service_id,
                quantity=quantity,
            )
            await chat_db.commit()
            product = details["product"]
            context.events.append({"type": "products", "products": [product]})
            return {
                "status": "confirmation_required",
                "action": "add",
                "service_id": service_id,
                "quantity": quantity,
                "product": product,
                "message": (
                    "Nothing has been added yet. Ask the visitor to confirm before "
                    "calling add_to_cart again."
                ),
            }

        result = await run_in_threadpool(
            lambda: _exec_add(context, service_id, quantity)
        )
        if result.get("status") == "added":
            await _consume_pending_action(chat_db, pending)
            await chat_db.commit()
            cart = result["cart"]
            context.events.append(
                {
                    "type": "cart_updated",
                    "action": "add",
                    "cart": cart,
                    "count": cart.get("item_count", 0),
                }
            )
            if cart.get("cart_token"):
                context.new_cart_token = cart["cart_token"]
        return result

    if name == "remove_from_cart":
        try:
            item_id = int(arguments.get("item_id"))
        except (TypeError, ValueError):
            return {"status": "error", "message": "item_id must be a number."}
        pending = await _get_pending_action(chat_db, context.session_id)
        confirmed = (
            is_affirmative(context.latest_user_message)
            and pending is not None
            and pending.intent == "remove"
            and pending.item_id == item_id
        )
        if not confirmed:
            cart_result = await run_in_threadpool(
                lambda: _exec_view_cart(context)
            )
            cart = cart_result.get("cart") or {}
            target = next(
                (
                    line
                    for line in cart.get("lines", [])
                    if int(line.get("item_id", 0)) == item_id
                ),
                None,
            )
            if target is None:
                return {"status": "not_found", "message": "That cart item was not found."}
            await _replace_pending_action(
                chat_db, context, intent="remove", item_id=item_id
            )
            await chat_db.commit()
            return {
                "status": "confirmation_required",
                "action": "remove",
                "item_id": item_id,
                "item": target,
                "message": (
                    "Nothing has been removed yet. Ask the visitor to confirm before "
                    "calling remove_from_cart again."
                ),
            }

        result = await run_in_threadpool(
            lambda: _exec_remove(context, item_id)
        )
        if result.get("status") == "removed":
            await _consume_pending_action(chat_db, pending)
            await chat_db.commit()
            cart = result["cart"]
            context.events.append(
                {
                    "type": "cart_updated",
                    "action": "remove",
                    "cart": cart,
                    "count": cart.get("item_count", 0),
                }
            )
            if cart.get("cart_token"):
                context.new_cart_token = cart["cart_token"]
        return result

    return {"status": "error", "message": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Synchronous executors (run in a worker thread with their own main-DB session)
# ---------------------------------------------------------------------------


def _exec_search(query: str, limit: int) -> dict[str, Any]:
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        return _tool_search_products(db, query, limit)
    finally:
        db.close()


def _exec_details(service_id: int | None, slug: str | None) -> dict[str, Any]:
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        return _tool_get_product_details(db, service_id, slug)
    finally:
        db.close()


def _exec_view_cart(context: ToolContext) -> dict[str, Any]:
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        user = _load_cart_user(db, context.user_id)
        return _tool_view_cart(db, user, context.cart_token)
    finally:
        db.close()


def _exec_add(context: ToolContext, service_id: int, quantity: int) -> dict[str, Any]:
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        user = _load_cart_user(db, context.user_id)
        return _tool_add_to_cart(db, user, context.cart_token, service_id, quantity)
    finally:
        db.close()


def _exec_remove(context: ToolContext, item_id: int) -> dict[str, Any]:
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        user = _load_cart_user(db, context.user_id)
        return _tool_remove_from_cart(db, user, context.cart_token, item_id)
    finally:
        db.close()


def tool_result_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
