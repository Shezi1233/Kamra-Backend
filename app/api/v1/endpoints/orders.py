from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models import User
from app.repositories.commerce import CommerceRepository
from app.repositories.users import UserRepository
from app.schemas.commerce import (
    CheckoutRequest,
    CheckoutResponse,
    NotificationOut,
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    StatusHistoryOut,
    PaymentOut,
    UserDashboardOut,
)
from app.schemas.common import Message
from app.services.admin_service import AdminService, order_out
from app.services.checkout_service import CheckoutService

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    return CheckoutService(db).checkout(user, payload)


@router.get("/orders", response_model=list[OrderOut])
def my_orders(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[OrderOut]:
    orders = CommerceRepository(db).list_user_orders(user.id)
    return [order_out(order, user) for order in orders]


@router.get("/orders/track", response_model=OrderDetailOut)
def track_order(
    tracking: str = Query(min_length=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    order = CommerceRepository(db).get_order_by_tracking(user.id, tracking.strip())
    if not order:
        raise HTTPException(status_code=404, detail="No order found for that tracking ID.")
    data = OrderDetailOut(**order_out(order, user).model_dump())
    data.items = [OrderItemOut.model_validate(item) for item in order.items]
    data.history = [
        StatusHistoryOut.model_validate(entry)
        for entry in sorted(order.history, key=lambda item: item.id, reverse=True)
    ]
    data.payments = [PaymentOut.model_validate(payment) for payment in order.payments]
    return data


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def my_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    order = CommerceRepository(db).get_user_order(user.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    data = OrderDetailOut(**order_out(order, user).model_dump())
    data.items = [OrderItemOut.model_validate(item) for item in order.items]
    data.history = [
        StatusHistoryOut.model_validate(entry)
        for entry in sorted(order.history, key=lambda item: item.id, reverse=True)
    ]
    data.payments = [PaymentOut.model_validate(payment) for payment in order.payments]
    return data


@router.get("/dashboard", response_model=UserDashboardOut)
def dashboard(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserDashboardOut:
    return AdminService(db).user_dashboard(user)


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[NotificationOut]:
    return [
        NotificationOut.model_validate(note)
        for note in UserRepository(db).list_notifications(user.id)
    ]


@router.post("/notifications/read", response_model=Message)
def mark_notifications_read(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Message:
    UserRepository(db).mark_notifications_read(user.id)
    return Message(detail="Notifications marked as read.")
