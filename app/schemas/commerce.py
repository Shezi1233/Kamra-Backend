from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.catalog import ServiceOut
from app.schemas.common import ORMModel


class CartLineOut(ServiceOut):
    quantity: int
    item_id: int


class CartOut(BaseModel):
    lines: list[CartLineOut]
    subtotal: Decimal
    has_quote: bool
    item_count: int
    cart_token: str | None = None


class AddToCartRequest(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class UpdateCartRequest(BaseModel):
    # Either item_id -> quantity, used by the Next.js cart page.
    quantities: dict[int, int] = Field(default_factory=dict)


class CartCountOut(BaseModel):
    count: int


class CheckoutRequest(BaseModel):
    company: str | None = Field(default=None, max_length=200)
    requirements: str = Field(min_length=10, max_length=5000)
    notes: str | None = None
    payment_method: str = "Cash on Delivery"
    coupon: str | None = None


class CheckoutResponse(BaseModel):
    tracking_id: str
    order_id: int


class OrderItemOut(ORMModel):
    id: int
    order_id: int
    service_id: int | None = None
    service_title: str
    unit_price: Decimal | None = None
    quantity: int
    line_total: Decimal
    created_at: datetime | None = None


class PaymentOut(ORMModel):
    id: int
    order_id: int
    method: str
    amount: Decimal
    status: str
    reference: str | None = None
    created_at: datetime | None = None
    tracking_id: str | None = None
    order_total: Decimal | None = None
    customer: str | None = None


class StatusHistoryOut(ORMModel):
    id: int
    order_id: int
    previous_status: str | None = None
    new_status: str
    customer_note: str | None = None
    admin_id: int | None = None
    created_at: datetime | None = None
    admin_name: str | None = None


class OrderOut(ORMModel):
    id: int
    user_id: int
    tracking_id: str
    status: str
    payment_status: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    coupon_code: str | None = None
    company: str | None = None
    requirements: str | None = None
    notes: str | None = None
    internal_note: str | None = None
    expected_completion: date | None = None
    created_at: datetime
    updated_at: datetime | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class OrderDetailOut(OrderOut):
    items: list[OrderItemOut] = Field(default_factory=list)
    history: list[StatusHistoryOut] = Field(default_factory=list)
    payments: list[PaymentOut] = Field(default_factory=list)


class OrderUpdate(BaseModel):
    status: str | None = None
    payment_status: str | None = None
    customer_note: str | None = None
    internal_note: str | None = None
    expected_completion: date | None = None


class PaymentSummaryOut(PaymentOut):
    tracking_id: str
    customer: str


class CustomerOut(ORMModel):
    id: int
    full_name: str
    email: str
    phone: str | None = None
    is_active: int
    created_at: datetime | None = None
    order_count: int | None = None
    total_spent: Decimal | None = None


class CustomerDetailOut(CustomerOut):
    orders: list[OrderOut] = Field(default_factory=list)


class OrderStatusCounts(BaseModel):
    total: int
    active: int
    customers: int
    new_messages: int
    paid_revenue: Decimal


class ContactMessageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: str
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=10, max_length=5000)


class ContactMessageOut(ORMModel):
    id: int
    name: str
    email: str
    subject: str | None = None
    message: str
    status: str
    created_at: datetime | None = None


class ContactMessageUpdate(BaseModel):
    status: str


class NotificationOut(ORMModel):
    id: int
    user_id: int | None = None
    admin_id: int | None = None
    type: str
    message: str
    is_read: int
    created_at: datetime | None = None


class AdminDashboardOut(BaseModel):
    stats: OrderStatusCounts
    recent_orders: list[OrderOut]
    latest_messages: list[ContactMessageOut]


class UserDashboardOut(BaseModel):
    total_orders: int
    active_orders: int
    unread_notifications: int
    recent_orders: list[OrderOut]
    notifications: list[NotificationOut]
