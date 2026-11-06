from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.session_days)


def generate_cart_token() -> str:
    return secrets.token_hex(24)


TRACKING_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_tracking_id() -> str:
    year = datetime.now(timezone.utc).year
    suffix = "".join(secrets.choice(TRACKING_CHARS) for _ in range(6))
    return f"AG-{year}-{suffix}"
