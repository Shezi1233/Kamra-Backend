from __future__ import annotations

from fastapi import Response

from app.core.config import settings
from app.core.dependencies import ADMIN_COOKIE, CART_COOKIE, USER_COOKIE

SESSION_MAX_AGE = settings.session_days * 24 * 60 * 60


def set_session_cookie(response: Response, name: str, token: str) -> None:
    response.set_cookie(
        key=name,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def clear_session_cookie(response: Response, name: str) -> None:
    response.delete_cookie(
        key=name,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def set_user_cookie(response: Response, token: str) -> None:
    set_session_cookie(response, USER_COOKIE, token)


def clear_user_cookie(response: Response) -> None:
    clear_session_cookie(response, USER_COOKIE)


def set_admin_cookie(response: Response, token: str) -> None:
    set_session_cookie(response, ADMIN_COOKIE, token)


def clear_admin_cookie(response: Response) -> None:
    clear_session_cookie(response, ADMIN_COOKIE)


def set_cart_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CART_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain or None,
        path="/",
    )
