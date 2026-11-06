from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, cart, catalog, contact, orders

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(contact.router)
api_router.include_router(admin.router)
