from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_cart_token, get_optional_user
from app.database.connection import get_db
from app.models import User
from app.schemas.commerce import (
    AddToCartRequest,
    CartCountOut,
    CartOut,
    UpdateCartRequest,
)
from app.services.cart_service import CartService
from app.utils.cookies import set_cart_cookie

router = APIRouter(prefix="/cart", tags=["cart"])


def _maybe_set_token(
    response: Response, cart: CartOut, user: User | None, cart_token: str | None
) -> None:
    if not user and cart.cart_token and cart.cart_token != cart_token:
        set_cart_cookie(response, cart.cart_token)


@router.get("", response_model=CartOut)
def get_cart(
    response: Response,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = CartService(db).summary(user, cart_token)
    _maybe_set_token(response, cart, user, cart_token)
    return cart


@router.get("/count", response_model=CartCountOut)
def cart_count(
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartCountOut:
    return CartCountOut(count=CartService(db).count(user, cart_token))


@router.post("/items", response_model=CartOut)
def add_item(
    payload: AddToCartRequest,
    response: Response,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = CartService(db).add(user, cart_token, payload.service_id, payload.quantity)
    _maybe_set_token(response, cart, user, cart_token)
    return cart


@router.put("/quantities", response_model=CartOut)
def update_quantities(
    payload: UpdateCartRequest,
    response: Response,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = CartService(db).update(user, cart_token, payload.quantities)
    _maybe_set_token(response, cart, user, cart_token)
    return cart


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_item(
    item_id: int,
    response: Response,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = CartService(db).remove(user, cart_token, item_id)
    _maybe_set_token(response, cart, user, cart_token)
    return cart


@router.delete("", response_model=CartOut)
def clear_cart(
    response: Response,
    user: User | None = Depends(get_optional_user),
    cart_token: str | None = Depends(get_cart_token),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = CartService(db).clear(user, cart_token)
    _maybe_set_token(response, cart, user, cart_token)
    return cart
