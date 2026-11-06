from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.database.connection import get_db
from app.models import Admin, User
from app.repositories.users import UserRepository

USER_COOKIE = "kt_user_session"
ADMIN_COOKIE = "kt_admin_session"
CART_COOKIE = "kt_cart_token"


def _bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization") or ""
    if value.lower().startswith("bearer "):
        token = value[7:].strip()
        return token or None
    return None


def get_session_token(request: Request, cookie_name: str) -> str | None:
    return (
        _bearer_token(request)
        or request.cookies.get(cookie_name)
        or request.headers.get("X-Session-Token")
    )


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = get_session_token(request, USER_COOKIE)
    if not token:
        return None
    return UserRepository(db).valid_user_session(hash_token(token))


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_optional_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(
    request: Request, db: Session = Depends(get_db)
) -> Admin:
    token = get_session_token(request, ADMIN_COOKIE)
    admin = UserRepository(db).valid_admin_session(hash_token(token)) if token else None
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin


def get_cart_token(request: Request) -> str | None:
    return request.headers.get("X-Cart-Token") or request.cookies.get(CART_COOKIE)
