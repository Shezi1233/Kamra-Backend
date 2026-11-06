from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.repositories.content import ContentRepository
from app.repositories.users import UserRepository
from app.schemas.commerce import ContactMessageCreate
from app.schemas.common import Message

router = APIRouter(tags=["contact"])


@router.post("/contact", response_model=Message, status_code=status.HTTP_201_CREATED)
def submit_contact(
    payload: ContactMessageCreate, db: Session = Depends(get_db)
) -> Message:
    message = ContentRepository(db).create_message(payload)
    UserRepository(db).add_notification(
        notification_type="contact_message",
        message=f"New contact message from {message.name}",
    )
    return Message(detail="Message received. We will reply soon.")
