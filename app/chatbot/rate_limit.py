from __future__ import annotations

import hashlib

from fastapi import Request
from slowapi import Limiter


def rate_limit_key(request: Request) -> str:
    """Rate-limit per session token when present, otherwise per client IP.

    The token is hashed so raw credentials never end up in limiter storage or
    logs.
    """

    authorization = request.headers.get("Authorization") or ""
    token: str | None = None
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip() or None
    if not token:
        token = request.cookies.get("kt_user_session") or request.cookies.get(
            "kt_admin_session"
        )
    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        return f"token:{digest}"
    forwarded = request.headers.get("X-Forwarded-For")
    host = forwarded.split(",")[0].strip() if forwarded else None
    if not host:
        host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


limiter = Limiter(key_func=rate_limit_key, headers_enabled=False)
