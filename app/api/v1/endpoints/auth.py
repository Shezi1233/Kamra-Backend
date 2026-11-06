from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_cart_token, get_current_user, get_session_token
from app.core.dependencies import USER_COOKIE
from app.core.security import hash_token
from app.database.connection import get_db
from app.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import Message
from app.services.auth_service import AuthService
from app.utils.cookies import clear_user_cookie, set_user_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    user = AuthService(db).register(payload)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    cart_token: str | None = Depends(get_cart_token),
) -> TokenResponse:
    service = AuthService(db)
    token, user = service.login(payload, cart_token=cart_token)
    set_user_cookie(response, token)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Message:
    token = get_session_token(request, USER_COOKIE)
    AuthService(db).logout(token)
    clear_user_cookie(response)
    return Message(detail="Logged out.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    reset_link = AuthService(db).forgot_password(payload)
    return ForgotPasswordResponse(
        success=(
            "If an account exists for that email, a password reset link has been created "
            "(valid for 1 hour)."
        ),
        reset_link=reset_link,
    )


@router.post("/reset-password", response_model=Message)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> Message:
    AuthService(db).reset_password(payload)
    return Message(detail="Password updated.")


@router.patch("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    updated = AuthService(db).update_profile(user, payload)
    return UserOut.model_validate(updated)


@router.post("/change-password", response_model=Message)
def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    AuthService(db).change_password(user, payload)
    return Message(detail="Password changed.")
