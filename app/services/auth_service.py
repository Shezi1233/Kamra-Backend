from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    session_expiry,
    verify_password,
)
from app.models import Admin, User
from app.repositories.commerce import CommerceRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    AdminProfileUpdate,
    ForgotPasswordRequest,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.commerce = CommerceRepository(db)

    # ------------------------------------------------------------------- register
    def register(self, payload: RegisterRequest) -> User:
        email = str(payload.email).lower()
        if self.users.get_user_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        return self.users.create_user(payload, hash_password(payload.password))

    # ---------------------------------------------------------------------- login
    def login(
        self, payload: LoginRequest, *, cart_token: str | None = None
    ) -> tuple[str, User]:
        email = str(payload.email).lower()
        user = self.users.get_user_by_email(email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )
        if user.is_active != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is deactivated.",
            )

        token = generate_session_token()
        self.users.create_session(
            token_hash=hash_token(token),
            expires_at=session_expiry(),
            user_id=user.id,
        )
        if cart_token:
            guest = self.commerce.get_guest_cart(cart_token)
            if guest:
                user_cart = self.commerce.get_or_create_user_cart(user.id)
                self.commerce.merge_carts(guest, user_cart)
        return token, user

    def admin_login(self, payload: LoginRequest) -> tuple[str, Admin]:
        email = str(payload.email).lower()
        admin = self.users.get_admin_by_email(email)
        if not admin or not verify_password(payload.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )
        if admin.is_active != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is deactivated."
            )
        token = generate_session_token()
        self.users.create_session(
            token_hash=hash_token(token),
            expires_at=session_expiry(),
            admin_id=admin.id,
        )
        return token, admin

    def logout(self, token: str | None) -> None:
        if token:
            self.users.delete_session(hash_token(token))

    # -------------------------------------------------------------- password flow
    def forgot_password(self, payload: ForgotPasswordRequest) -> str | None:
        user = self.users.get_user_by_email(str(payload.email).lower())
        if not user:
            return None
        token = generate_session_token()
        self.users.set_reset_token(
            user,
            hash_token(token),
            datetime.now() + timedelta(hours=1),
        )
        base = settings.frontend_url.rstrip("/")
        return f"{base}/reset-password?token={token}"

    def reset_password(self, payload: ResetPasswordRequest) -> None:
        user = self.users.get_user_by_reset_token(hash_token(payload.token))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link is invalid or expired.",
            )
        self.users.set_password(user, hash_password(payload.password))

    def update_profile(self, user: User, payload: ProfileUpdate) -> User:
        return self.users.update_profile(user, payload.full_name, payload.phone)

    def change_password(self, user: User, payload: PasswordChange) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )
        self.users.set_password(user, hash_password(payload.password))

    def update_admin_profile(self, admin: Admin, payload: AdminProfileUpdate) -> Admin:
        admin.full_name = payload.full_name
        if payload.password:
            admin.password_hash = hash_password(payload.password)
        self.db.commit()
        self.db.refresh(admin)
        return admin
