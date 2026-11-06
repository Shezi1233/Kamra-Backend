from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generate_cart_token
from app.models import Service, User
from app.repositories.catalog import CatalogRepository
from app.repositories.commerce import CommerceRepository
from app.schemas.commerce import CartLineOut, CartOut
from app.services.catalog_service import service_out


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.commerce = CommerceRepository(db)
        self.catalog = CatalogRepository(db)

    def _lines(self, cart_id: int) -> tuple[list[CartLineOut], Decimal, bool]:
        lines: list[CartLineOut] = []
        subtotal = Decimal("0")
        has_quote = False
        for service, item in self.commerce.cart_service_rows(cart_id):
            line = CartLineOut(
                **service_out(service).model_dump(),
                quantity=item.quantity,
                item_id=item.id,
            )
            lines.append(line)
            if service.price is None:
                has_quote = True
            else:
                subtotal += Decimal(str(service.price)) * item.quantity
        return lines, subtotal, has_quote

    def summary(
        self, user: User | None, cart_token: str | None
    ) -> CartOut:
        if user:
            cart = self.commerce.get_or_create_user_cart(user.id)
            lines, subtotal, has_quote = self._lines(cart.id)
            return CartOut(
                lines=lines,
                subtotal=subtotal,
                has_quote=has_quote,
                item_count=sum(line.quantity for line in lines),
            )
        if cart_token:
            cart = self.commerce.get_guest_cart(cart_token)
            if cart:
                lines, subtotal, has_quote = self._lines(cart.id)
                return CartOut(
                    lines=lines,
                    subtotal=subtotal,
                    has_quote=has_quote,
                    item_count=sum(line.quantity for line in lines),
                    cart_token=cart_token,
                )
        return CartOut(lines=[], subtotal=Decimal("0"), has_quote=False, item_count=0)

    def _resolve_cart(self, user: User | None, cart_token: str | None):
        if user:
            return self.commerce.get_or_create_user_cart(user.id), None
        token = cart_token or generate_cart_token()
        return self.commerce.get_or_create_guest_cart(token), token

    def add(
        self, user: User | None, cart_token: str | None, service_id: int, quantity: int = 1
    ) -> CartOut:
        service = self.catalog.get_service(service_id)
        if not service or service.is_active != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That service is not available.",
            )
        cart, token = self._resolve_cart(user, cart_token)
        self.commerce.add_cart_item(cart.id, service_id, max(1, quantity))
        summary = self.summary(user, token)
        summary.cart_token = token
        return summary

    def update(
        self, user: User | None, cart_token: str | None, quantities: dict[int, int]
    ) -> CartOut:
        cart = (
            self.commerce.get_user_cart(user.id)
            if user
            else self.commerce.get_guest_cart(cart_token) if cart_token else None
        )
        if cart:
            for item_id, quantity in quantities.items():
                item = self.commerce.get_cart_item_by_id(cart.id, int(item_id))
                if item:
                    self.commerce.update_cart_item(item, int(quantity))
        return self.summary(user, cart_token)

    def remove(self, user: User | None, cart_token: str | None, item_id: int) -> CartOut:
        cart = (
            self.commerce.get_user_cart(user.id)
            if user
            else self.commerce.get_guest_cart(cart_token) if cart_token else None
        )
        if cart:
            item = self.commerce.get_cart_item_by_id(cart.id, item_id)
            if item:
                self.commerce.delete_cart_item(item)
        return self.summary(user, cart_token)

    def clear(self, user: User | None, cart_token: str | None) -> CartOut:
        cart = (
            self.commerce.get_user_cart(user.id)
            if user
            else self.commerce.get_guest_cart(cart_token) if cart_token else None
        )
        if cart:
            self.commerce.clear_cart(cart.id)
        return self.summary(user, cart_token)

    def count(self, user: User | None, cart_token: str | None) -> int:
        return self.summary(user, cart_token).item_count

    def active_services_in_cart(self, cart_id: int) -> list[tuple[Service, int]]:
        return [
            (service, item.quantity)
            for service, item in self.commerce.cart_service_rows(cart_id)
        ]
