from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.constants import PAYMENT_METHODS
from app.core.security import generate_tracking_id
from app.models import Order, OrderItem, OrderStatusHistory, Payment, User
from app.repositories.commerce import CommerceRepository
from app.schemas.commerce import CheckoutRequest, CheckoutResponse


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CheckoutService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.commerce = CommerceRepository(db)

    def _unique_tracking(self) -> str:
        for _ in range(30):
            candidate = generate_tracking_id()
            if not self.commerce.tracking_exists(candidate):
                return candidate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate a unique tracking ID.",
        )

    def checkout(self, user: User, payload: CheckoutRequest) -> CheckoutResponse:
        cart = self.commerce.get_user_cart(user.id)
        if not cart:
            raise HTTPException(status_code=400, detail="Your cart is empty.")
        rows = self.commerce.cart_service_rows(cart.id)
        if not rows:
            raise HTTPException(status_code=400, detail="Your cart is empty.")

        subtotal = Decimal("0")
        for service, item in rows:
            if service.price is not None:
                subtotal += Decimal(str(service.price)) * item.quantity
        subtotal = _money(subtotal)

        discount = Decimal("0")
        applied_coupon: str | None = None
        if payload.coupon:
            coupon = self.commerce.valid_coupon(payload.coupon.strip())
            if not coupon:
                raise HTTPException(
                    status_code=400, detail="Coupon code is invalid or expired."
                )
            if coupon.discount_type == "percent":
                discount = subtotal * (Decimal(str(coupon.discount_value)) / Decimal("100"))
            else:
                discount = min(Decimal(str(coupon.discount_value)), subtotal)
            discount = _money(discount)
            applied_coupon = coupon.code

        total = _money(max(Decimal("0"), subtotal - discount))
        method = (
            payload.payment_method
            if payload.payment_method in PAYMENT_METHODS
            else PAYMENT_METHODS[0]
        )

        try:
            tracking_id = self._unique_tracking()
            order = Order(
                user_id=user.id,
                tracking_id=tracking_id,
                status="Order Placed",
                payment_status="Pending",
                subtotal=subtotal,
                discount=discount,
                total=total,
                coupon_code=applied_coupon,
                company=payload.company,
                requirements=payload.requirements,
                notes=payload.notes,
            )
            order = self.commerce.create_order(order)

            for service, item in rows:
                unit_price = (
                    None if service.price is None else Decimal(str(service.price))
                )
                line_total = (
                    Decimal("0")
                    if unit_price is None
                    else _money(unit_price * item.quantity)
                )
                self.commerce.add_order_item(
                    OrderItem(
                        order_id=order.id,
                        service_id=service.id,
                        service_title=service.title,
                        unit_price=unit_price,
                        quantity=item.quantity,
                        line_total=line_total,
                    )
                )

            self.commerce.add_status_history(
                OrderStatusHistory(
                    order_id=order.id,
                    previous_status=None,
                    new_status="Order Placed",
                    customer_note="Order received.",
                )
            )
            self.commerce.add_payment(
                Payment(order_id=order.id, method=method, amount=total, status="Pending")
            )
            self.commerce.clear_cart(cart.id)
            self.commerce.commit()

            from app.repositories.users import UserRepository

            users = UserRepository(self.db)
            users.add_notification(
                notification_type="order_placed",
                message=f"Your order {tracking_id} has been placed.",
                user_id=user.id,
            )
            users.add_notification(
                notification_type="new_order",
                message=f"New order {tracking_id} placed.",
            )
            return CheckoutResponse(tracking_id=tracking_id, order_id=order.id)
        except HTTPException:
            self.commerce.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            self.commerce.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Checkout failed. Please try again.",
            ) from exc
