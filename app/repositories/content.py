from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContactMessage
from app.schemas.commerce import ContactMessageCreate


class ContentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_message(self, payload: ContactMessageCreate) -> ContactMessage:
        message = ContactMessage(
            name=payload.name,
            email=payload.email.lower(),
            subject=payload.subject,
            message=payload.message,
            status="new",
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, status: str | None = None, limit: int = 200) -> list[ContactMessage]:
        stmt = select(ContactMessage).order_by(ContactMessage.id.desc()).limit(limit)
        if status:
            stmt = stmt.where(ContactMessage.status == status)
        return list(self.db.scalars(stmt).all())

    def get_message(self, message_id: int) -> ContactMessage | None:
        return self.db.get(ContactMessage, message_id)

    def update_status(self, message: ContactMessage, status: str) -> ContactMessage:
        message.status = status
        self.db.commit()
        self.db.refresh(message)
        return message

    def delete_message(self, message: ContactMessage) -> None:
        self.db.delete(message)
        self.db.commit()
