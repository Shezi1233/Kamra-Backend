from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Admin, AppSession, Notification, User
from app.schemas.auth import RegisterRequest


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------------------------------------------------------------- users
    def get_user(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def create_user(self, payload: RegisterRequest, password_hash: str) -> User:
        user = User(
            full_name=payload.full_name,
            email=str(payload.email).lower(),
            phone=payload.phone,
            password_hash=password_hash,
            is_active=1,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        user.reset_token = None
        user.reset_expires = None
        self.db.commit()

    def set_reset_token(self, user: User, token_hash: str, expires: datetime) -> None:
        user.reset_token = token_hash
        user.reset_expires = expires
        self.db.commit()

    def get_user_by_reset_token(self, token_hash: str) -> User | None:
        return self.db.scalar(
            select(User).where(
                User.reset_token == token_hash,
                User.reset_expires > datetime.now(),
            )
        )

    def update_profile(self, user: User, full_name: str, phone: str | None) -> User:
        user.full_name = full_name
        user.phone = phone
        self.db.commit()
        self.db.refresh(user)
        return user

    def toggle_user(self, user: User) -> User:
        user.is_active = 0 if user.is_active == 1 else 1
        self.db.commit()
        self.db.refresh(user)
        return user

    # --------------------------------------------------------------------- admins
    def get_admin(self, admin_id: int) -> Admin | None:
        return self.db.get(Admin, admin_id)

    def get_admin_by_email(self, email: str) -> Admin | None:
        return self.db.scalar(select(Admin).where(Admin.email == email.lower()))

    # ------------------------------------------------------------------- sessions
    def create_session(
        self,
        *,
        token_hash: str,
        expires_at: datetime,
        user_id: int | None = None,
        admin_id: int | None = None,
    ) -> AppSession:
        session = AppSession(
            token_hash=token_hash,
            user_id=user_id,
            admin_id=admin_id,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.commit()
        return session

    def valid_user_session(self, token_hash: str) -> User | None:
        return self.db.scalar(
            select(User)
            .join(AppSession, AppSession.user_id == User.id)
            .where(
                AppSession.token_hash == token_hash,
                AppSession.expires_at > datetime.now(),
                User.is_active == 1,
            )
            .limit(1)
        )

    def valid_admin_session(self, token_hash: str) -> Admin | None:
        return self.db.scalar(
            select(Admin)
            .join(AppSession, AppSession.admin_id == Admin.id)
            .where(
                AppSession.token_hash == token_hash,
                AppSession.expires_at > datetime.now(),
                Admin.is_active == 1,
            )
            .limit(1)
        )

    def delete_session(self, token_hash: str) -> None:
        session = self.db.get(AppSession, token_hash)
        if session:
            self.db.delete(session)
            self.db.commit()

    # -------------------------------------------------------------- notifications
    def add_notification(
        self,
        *,
        notification_type: str,
        message: str,
        user_id: int | None = None,
        admin_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            admin_id=admin_id,
            type=notification_type,
            message=message,
        )
        self.db.add(notification)
        self.db.commit()
        return notification

    def list_notifications(self, user_id: int, limit: int = 100) -> list[Notification]:
        return list(
            self.db.scalars(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.id.desc())
                .limit(limit)
            ).all()
        )

    def mark_notifications_read(self, user_id: int) -> None:
        for notification in self.db.scalars(
            select(Notification).where(
                Notification.user_id == user_id, Notification.is_read == 0
            )
        ).all():
            notification.is_read = 1
        self.db.commit()
