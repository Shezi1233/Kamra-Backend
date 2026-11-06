from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Cart,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Service,
    User,
)


class CommerceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------------------------------------------------- carts
    def get_user_cart(self, user_id: int) -> Cart | None:
        return self.db.scalar(select(Cart).where(Cart.user_id == user_id).limit(1))

    def get_guest_cart(self, token: str) -> Cart | None:
        return self.db.scalar(
            select(Cart).where(Cart.user_id.is_(None), Cart.session_token == token).limit(1)
        )

    def create_cart(self, *, user_id: int | None = None, session_token: str | None = None) -> Cart:
        cart = Cart(user_id=user_id, session_token=session_token)
        self.db.add(cart)
        self.db.commit()
        self.db.refresh(cart)
        return cart

    def get_or_create_user_cart(self, user_id: int) -> Cart:
        return self.get_user_cart(user_id) or self.create_cart(user_id=user_id)

    def get_or_create_guest_cart(self, token: str) -> Cart:
        return self.get_guest_cart(token) or self.create_cart(session_token=token)

    def cart_service_rows(self, cart_id: int) -> list[tuple[Service, CartItem]]:
        stmt = (
            select(Service, CartItem)
            .join(CartItem, CartItem.service_id == Service.id)
            .options(joinedload(Service.category))
            .where(CartItem.cart_id == cart_id, Service.is_active == 1)
            .order_by(CartItem.id)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt).unique().all()]

    def get_cart_item(self, cart_id: int, service_id: int) -> CartItem | None:
        return self.db.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart_id, CartItem.service_id == service_id
            )
        )

    def add_cart_item(self, cart_id: int, service_id: int, quantity: int = 1) -> CartItem:
        item = self.get_cart_item(cart_id, service_id)
        if item:
            item.quantity = min(99, item.quantity + quantity)
        else:
            item = CartItem(cart_id=cart_id, service_id=service_id, quantity=quantity)
            self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_cart_item(self, item: CartItem, quantity: int) -> None:
        if quantity <= 0:
            self.db.delete(item)
        else:
            item.quantity = min(99, quantity)
        self.db.commit()

    def get_cart_item_by_id(self, cart_id: int, item_id: int) -> CartItem | None:
        return self.db.scalar(
            select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
        )

    def delete_cart_item(self, item: CartItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def clear_cart(self, cart_id: int) -> None:
        for item in self.db.scalars(select(CartItem).where(CartItem.cart_id == cart_id)).all():
            self.db.delete(item)
        self.db.commit()

    def merge_carts(self, source: Cart, target: Cart) -> None:
        for item in self.db.scalars(
            select(CartItem).where(CartItem.cart_id == source.id)
        ).all():
            existing = self.get_cart_item(target.id, item.service_id)
            if existing:
                existing.quantity = min(99, existing.quantity + item.quantity)
            else:
                self.db.add(
                    CartItem(
                        cart_id=target.id,
                        service_id=item.service_id,
                        quantity=item.quantity,
                    )
                )
            self.db.delete(item)
        self.db.delete(source)
        self.db.commit()

    # --------------------------------------------------------------------- coupons
    def valid_coupon(self, code: str) -> Coupon | None:
        return self.db.scalar(
            select(Coupon).where(
                Coupon.code == code,
                Coupon.is_active == 1,
                or_(Coupon.expires_at.is_(None), Coupon.expires_at > datetime.now()),
            )
        )

    # ---------------------------------------------------------------------- orders
    def tracking_exists(self, tracking_id: str) -> bool:
        return (
            self.db.scalar(select(Order.id).where(Order.tracking_id == tracking_id)) is not None
        )

    def create_order(self, order: Order) -> Order:
        self.db.add(order)
        self.db.flush()
        return order

    def add_order_item(self, item: OrderItem) -> None:
        self.db.add(item)

    def add_status_history(self, entry: OrderStatusHistory) -> None:
        self.db.add(entry)

    def add_payment(self, payment: Payment) -> None:
        self.db.add(payment)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def get_order(self, order_id: int) -> Order | None:
        return self.db.scalar(
            select(Order)
            .options(
                joinedload(Order.items),
                joinedload(Order.history),
                joinedload(Order.payments),
            )
            .where(Order.id == order_id)
        )

    def get_user_order(self, user_id: int, order_id: int) -> Order | None:
        return self.db.scalar(
            select(Order)
            .options(
                joinedload(Order.items),
                joinedload(Order.history),
                joinedload(Order.payments),
            )
            .where(Order.id == order_id, Order.user_id == user_id)
        )

    def get_order_by_tracking(self, user_id: int, tracking_id: str) -> Order | None:
        return self.db.scalar(
            select(Order)
            .options(
                joinedload(Order.items),
                joinedload(Order.history),
                joinedload(Order.payments),
            )
            .where(Order.tracking_id == tracking_id, Order.user_id == user_id)
        )

    def order_by_tracking_any(self, tracking_id: str) -> Order | None:
        return self.db.scalar(select(Order).where(Order.tracking_id == tracking_id))

    def list_user_orders(self, user_id: int, limit: int = 200) -> list[Order]:
        return list(
            self.db.scalars(
                select(Order)
                .where(Order.user_id == user_id)
                .order_by(Order.id.desc())
                .limit(limit)
            ).all()
        )

    def list_orders(
        self, *, q: str | None = None, status: str | None = None, limit: int = 200
    ) -> list[Order]:
        stmt = (
            select(Order)
            .options(joinedload(Order.items), joinedload(Order.history), joinedload(Order.payments))
            .order_by(Order.id.desc())
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.join(User, User.id == Order.user_id).where(
                or_(
                    Order.tracking_id.like(like),
                    User.full_name.like(like),
                    User.email.like(like),
                )
            )
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).unique().all())

    def update_order(
        self,
        order: Order,
        *,
        status: str,
        payment_status: str,
        internal_note: str | None,
        expected_completion: date | None,
    ) -> None:
        order.status = status
        order.payment_status = payment_status
        order.internal_note = internal_note
        order.expected_completion = expected_completion
        self.db.commit()

    def sync_payment_status(self, order_id: int, payment_status: str) -> None:
        mapped = (
            "Paid" if payment_status == "Paid" else "Failed" if payment_status == "Failed" else "Pending"
        )
        for payment in self.db.scalars(
            select(Payment).where(Payment.order_id == order_id)
        ).all():
            payment.status = mapped
        self.db.commit()

    def list_payments(self, limit: int = 200) -> list[Payment]:
        return list(
            self.db.scalars(select(Payment).order_by(Payment.id.desc()).limit(limit)).all()
        )

    def payment_rows(self, limit: int = 200) -> list[tuple[Payment, Order, User]]:
        stmt = (
            select(Payment, Order, User)
            .join(Order, Order.id == Payment.order_id)
            .join(User, User.id == Order.user_id)
            .order_by(Payment.id.desc())
            .limit(limit)
        )
        return [tuple(row) for row in self.db.execute(stmt).all()]

    # ------------------------------------------------------------------- customers
    def list_customers(self, q: str | None = None, limit: int = 200) -> list[tuple]:
        stmt = (
            select(
                User,
                func.count(func.distinct(Order.id)).label("order_count"),
                func.coalesce(func.sum(Order.total), 0).label("total_spent"),
            )
            .outerjoin(Order, Order.user_id == User.id)
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(User.full_name.like(like), User.email.like(like)))
        stmt = stmt.group_by(User.id).order_by(User.id.desc()).limit(limit)
        return [tuple(row) for row in self.db.execute(stmt).all()]

    def get_customer(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    # ------------------------------------------------------------------ dashboards
    def user_dashboard(self, user_id: int) -> dict:
        total_orders = int(
            self.db.scalar(select(func.count(Order.id)).where(Order.user_id == user_id)) or 0
        )
        active_orders = int(
            self.db.scalar(
                select(func.count(Order.id)).where(
                    Order.user_id == user_id,
                    Order.status.notin_(["Delivered", "Completed", "Cancelled"]),
                )
            )
            or 0
        )
        from app.models import Notification

        unread = int(
            self.db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id, Notification.is_read == 0
                )
            )
            or 0
        )
        recent = list(
            self.db.scalars(
                select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(5)
            ).all()
        )
        notifications = list(
            self.db.scalars(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.id.desc())
                .limit(4)
            ).all()
        )
        return {
            "total_orders": total_orders,
            "active_orders": active_orders,
            "unread_notifications": unread,
            "recent_orders": recent,
            "notifications": notifications,
        }

    def admin_dashboard(self) -> dict:
        from app.models import ContactMessage

        total_orders = int(self.db.scalar(select(func.count(Order.id))) or 0)
        active_orders = int(
            self.db.scalar(
                select(func.count(Order.id)).where(
                    Order.status.notin_(["Delivered", "Completed", "Cancelled"])
                )
            )
            or 0
        )
        customers = int(self.db.scalar(select(func.count(User.id))) or 0)
        new_messages = int(
            self.db.scalar(
                select(func.count(ContactMessage.id)).where(ContactMessage.status == "new")
            )
            or 0
        )
        paid_revenue = Decimal(
            str(
                self.db.scalar(
                    select(func.coalesce(func.sum(Order.total), 0)).where(
                        Order.payment_status == "Paid"
                    )
                )
                or 0
            )
        )
        recent = list(
            self.db.scalars(
                select(Order).order_by(Order.id.desc()).limit(6)
            ).all()
        )
        latest_messages = list(
            self.db.scalars(
                select(ContactMessage).order_by(ContactMessage.id.desc()).limit(4)
            ).all()
        )
        return {
            "stats": {
                "total": total_orders,
                "active": active_orders,
                "customers": customers,
                "new_messages": new_messages,
                "paid_revenue": paid_revenue,
            },
            "recent_orders": recent,
            "latest_messages": latest_messages,
        }
