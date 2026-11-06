from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.constants import ORDER_STATUSES, PAYMENT_STATUSES
from app.models import Order, User
from app.repositories.catalog import CatalogRepository
from app.repositories.commerce import CommerceRepository
from app.repositories.content import ContentRepository
from app.repositories.users import UserRepository
from app.schemas.commerce import (
    AdminDashboardOut,
    ContactMessageOut,
    CustomerDetailOut,
    CustomerOut,
    NotificationOut,
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    OrderUpdate,
    PaymentSummaryOut,
    StatusHistoryOut,
    UserDashboardOut,
)


def order_out(order: Order, user: User | None = None) -> OrderOut:
    data = OrderOut.model_validate(order)
    if user is not None:
        data.full_name = user.full_name
        data.email = user.email
        data.phone = user.phone
    return data


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.commerce = CommerceRepository(db)
        self.content = ContentRepository(db)
        self.catalog = CatalogRepository(db)
        self.users = UserRepository(db)

    # ---------------------------------------------------------------------- orders
    def _user_map(self, orders: list[Order]) -> dict[int, User]:
        ids = {order.user_id for order in orders}
        result: dict[int, User] = {}
        for user_id in ids:
            user = self.users.get_user(user_id)
            if user:
                result[user_id] = user
        return result

    def list_orders(self, *, q: str | None = None, status: str | None = None) -> list[OrderOut]:
        orders = self.commerce.list_orders(q=q, status=status)
        users = self._user_map(orders)
        return [order_out(order, users.get(order.user_id)) for order in orders]

    def get_order(self, order_id: int) -> OrderDetailOut:
        order = self.commerce.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")
        user = self.users.get_user(order.user_id)
        data = OrderDetailOut(**order_out(order, user).model_dump())
        data.items = [OrderItemOut.model_validate(item) for item in order.items]
        admin_names = {}
        for entry in order.history:
            if entry.admin_id:
                admin = self.users.get_admin(entry.admin_id)
                if admin:
                    admin_names[entry.admin_id] = admin.full_name
        data.history = []
        for entry in sorted(order.history, key=lambda item: item.id, reverse=True):
            history = StatusHistoryOut.model_validate(entry)
            history.admin_name = admin_names.get(entry.admin_id or 0)
            data.history.append(history)
        data.payments = [
            PaymentSummaryOut(
                **{
                    "id": payment.id,
                    "order_id": payment.order_id,
                    "method": payment.method,
                    "amount": payment.amount,
                    "status": payment.status,
                    "reference": payment.reference,
                    "created_at": payment.created_at,
                    "tracking_id": order.tracking_id,
                    "customer": user.full_name if user else "",
                    "order_total": payment.amount,
                }
            )
            for payment in sorted(order.payments, key=lambda item: item.id, reverse=True)
        ]
        return data

    def update_order(self, order_id: int, payload: OrderUpdate, admin_id: int) -> OrderDetailOut:
        order = self.commerce.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")
        new_status = payload.status or order.status
        payment_status = payload.payment_status or order.payment_status
        if new_status not in ORDER_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status.")
        if payment_status not in PAYMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid payment status.")
        previous_status = order.status
        self.commerce.update_order(
            order,
            status=new_status,
            payment_status=payment_status,
            internal_note=payload.internal_note,
            expected_completion=payload.expected_completion,
        )
        self.commerce.sync_payment_status(order_id, payment_status)
        if new_status != previous_status:
            from app.models import OrderStatusHistory

            self.commerce.add_status_history(
                OrderStatusHistory(
                    order_id=order_id,
                    previous_status=previous_status,
                    new_status=new_status,
                    customer_note=payload.customer_note,
                    admin_id=admin_id,
                )
            )
            self.commerce.commit()
            note = f"Your order {order.tracking_id} is now: {new_status}"
            if payload.customer_note:
                note += f" — {payload.customer_note}"
            self.users.add_notification(
                notification_type="order_update", message=note, user_id=order.user_id
            )
        return self.get_order(order_id)

    # ------------------------------------------------------------------- customers
    def list_customers(self, q: str | None = None) -> list[CustomerOut]:
        items = []
        for user, order_count, total_spent in self.commerce.list_customers(q):
            data = CustomerOut.model_validate(user)
            data.order_count = int(order_count)
            data.total_spent = Decimal(str(total_spent))
            items.append(data)
        return items

    def get_customer(self, user_id: int) -> CustomerDetailOut:
        user = self.commerce.get_customer(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Customer not found.")
        orders = self.commerce.list_user_orders(user_id)
        data = CustomerDetailOut(**CustomerOut.model_validate(user).model_dump())
        data.orders = [order_out(order, user) for order in orders]
        data.order_count = len(orders)
        data.total_spent = sum((order.total for order in orders), Decimal("0"))
        return data

    def toggle_customer(self, user_id: int) -> CustomerOut:
        user = self.commerce.get_customer(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return CustomerOut.model_validate(self.users.toggle_user(user))

    # -------------------------------------------------------------------- payments
    def list_payments(self) -> list[PaymentSummaryOut]:
        rows = self.commerce.payment_rows()
        return [
            PaymentSummaryOut(
                id=payment.id,
                order_id=payment.order_id,
                method=payment.method,
                amount=payment.amount,
                status=payment.status,
                reference=payment.reference,
                created_at=payment.created_at,
                tracking_id=order.tracking_id,
                customer=user.full_name,
                order_total=order.total,
            )
            for payment, order, user in rows
        ]

    # -------------------------------------------------------------------- messages
    def list_messages(self, status: str | None = None) -> list[ContactMessageOut]:
        return [
            ContactMessageOut.model_validate(message)
            for message in self.content.list_messages(status=status)
        ]

    def update_message(self, message_id: int, status: str) -> ContactMessageOut:
        if status not in ("new", "read", "archived"):
            raise HTTPException(status_code=400, detail="Invalid message status.")
        message = self.content.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found.")
        return ContactMessageOut.model_validate(self.content.update_status(message, status))

    def delete_message(self, message_id: int) -> None:
        message = self.content.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found.")
        self.content.delete_message(message)

    # ------------------------------------------------------------------- dashboard
    def dashboard(self) -> AdminDashboardOut:
        data = self.commerce.admin_dashboard()
        recent = data["recent_orders"]
        users = self._user_map(recent)
        return AdminDashboardOut(
            stats=data["stats"],
            recent_orders=[order_out(order, users.get(order.user_id)) for order in recent],
            latest_messages=[
                ContactMessageOut.model_validate(message)
                for message in data["latest_messages"]
            ],
        )

    def user_dashboard(self, user: User) -> UserDashboardOut:
        data = self.commerce.user_dashboard(user.id)
        return UserDashboardOut(
            total_orders=data["total_orders"],
            active_orders=data["active_orders"],
            unread_notifications=data["unread_notifications"],
            recent_orders=[order_out(order, user) for order in data["recent_orders"]],
            notifications=[
                NotificationOut.model_validate(note) for note in data["notifications"]
            ],
        )
