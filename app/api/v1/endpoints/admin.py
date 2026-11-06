from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import ADMIN_COOKIE, get_current_admin, get_session_token
from app.database.connection import get_db
from app.models import Admin
from app.schemas.auth import (
    AdminOut,
    AdminProfileUpdate,
    LoginRequest,
    TokenResponse,
)
from app.schemas.catalog import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    PortfolioCreate,
    PortfolioOut,
    PortfolioUpdate,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
    SettingsOut,
    SettingsUpdate,
    TestimonialCreate,
    TestimonialOut,
)
from app.schemas.commerce import (
    AdminDashboardOut,
    ContactMessageOut,
    CustomerDetailOut,
    CustomerOut,
    OrderDetailOut,
    OrderOut,
    OrderUpdate,
    PaymentSummaryOut,
)
from app.schemas.common import Message
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.upload_service import UploadService
from app.utils.cookies import clear_admin_cookie, set_admin_cookie

router = APIRouter(prefix="/admin", tags=["admin"])
admin_required = Depends(get_current_admin)


# ----------------------------------------------------------------------- auth
@router.post("/auth/login", response_model=TokenResponse)
def admin_login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    token, admin = AuthService(db).admin_login(payload)
    set_admin_cookie(response, token)
    return TokenResponse(access_token=token, admin=AdminOut.model_validate(admin))


@router.post("/auth/logout", response_model=Message)
def admin_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Message:
    token = get_session_token(request, ADMIN_COOKIE)
    AuthService(db).logout(token)
    clear_admin_cookie(response)
    return Message(detail="Logged out.")


@router.get("/auth/me", response_model=AdminOut)
def admin_me(admin: Admin = Depends(get_current_admin)) -> AdminOut:
    return AdminOut.model_validate(admin)


@router.patch("/auth/profile", response_model=AdminOut)
def admin_profile(
    payload: AdminProfileUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminOut:
    updated = AuthService(db).update_admin_profile(admin, payload)
    return AdminOut.model_validate(updated)


# ----------------------------------------------------------------- dashboard
@router.get("/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> AdminDashboardOut:
    return AdminService(db).dashboard()


# ------------------------------------------------------------------- services
@router.get("/services", response_model=list[ServiceOut])
def admin_services(
    q: str | None = None,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> list[ServiceOut]:
    return CatalogService(db).list_services(active_only=False, q=q, sort="newest")


@router.get("/services/{service_id}", response_model=ServiceOut)
def admin_service(
    service_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> ServiceOut:
    return CatalogService(db).get_service(str(service_id))


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def admin_create_service(
    payload: ServiceCreate, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> ServiceOut:
    return CatalogService(db).create_service(payload)


@router.put("/services/{service_id}", response_model=ServiceOut)
def admin_update_service(
    service_id: int,
    payload: ServiceUpdate,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> ServiceOut:
    return CatalogService(db).update_service(service_id, payload)


@router.delete("/services/{service_id}", response_model=Message)
def admin_delete_service(
    service_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> Message:
    result = CatalogService(db).delete_service(service_id)
    return Message(detail=result["detail"])


# ----------------------------------------------------------------- categories
@router.get("/categories", response_model=list[CategoryOut])
def admin_categories(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> list[CategoryOut]:
    return CatalogService(db).list_categories(active_only=False)


@router.get("/categories/{category_id}", response_model=CategoryOut)
def admin_category(
    category_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> CategoryOut:
    service = CatalogService(db)
    category = service.repo.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")
    return CategoryOut.model_validate(category)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def admin_create_category(
    payload: CategoryCreate, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> CategoryOut:
    return CatalogService(db).create_category(payload)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def admin_update_category(
    category_id: int,
    payload: CategoryUpdate,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> CategoryOut:
    return CatalogService(db).update_category(category_id, payload)


@router.delete("/categories/{category_id}", response_model=Message)
def admin_delete_category(
    category_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> Message:
    CatalogService(db).delete_category(category_id)
    return Message(detail="Category deleted.")


# ------------------------------------------------------------------ portfolio
@router.get("/portfolio", response_model=list[PortfolioOut])
def admin_portfolio(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> list[PortfolioOut]:
    return CatalogService(db).list_portfolio(active_only=False)


@router.get("/portfolio/{project_id}", response_model=PortfolioOut)
def admin_portfolio_item(
    project_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> PortfolioOut:
    return CatalogService(db).get_portfolio(project_id)


@router.post("/portfolio", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def admin_create_portfolio(
    payload: PortfolioCreate, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> PortfolioOut:
    return CatalogService(db).create_portfolio(payload)


@router.put("/portfolio/{project_id}", response_model=PortfolioOut)
def admin_update_portfolio(
    project_id: int,
    payload: PortfolioUpdate,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> PortfolioOut:
    return CatalogService(db).update_portfolio(project_id, payload)


@router.delete("/portfolio/{project_id}", response_model=Message)
def admin_delete_portfolio(
    project_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> Message:
    CatalogService(db).delete_portfolio(project_id)
    return Message(detail="Project deleted.")


# --------------------------------------------------------------- testimonials
@router.get("/testimonials", response_model=list[TestimonialOut])
def admin_testimonials(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> list[TestimonialOut]:
    return CatalogService(db).list_testimonials(approved_only=False)


@router.post("/testimonials", response_model=TestimonialOut, status_code=status.HTTP_201_CREATED)
def admin_create_testimonial(
    payload: TestimonialCreate, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> TestimonialOut:
    return CatalogService(db).create_testimonial(payload)


@router.post("/testimonials/{testimonial_id}/toggle", response_model=TestimonialOut)
def admin_toggle_testimonial(
    testimonial_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> TestimonialOut:
    return CatalogService(db).toggle_testimonial(testimonial_id)


@router.delete("/testimonials/{testimonial_id}", response_model=Message)
def admin_delete_testimonial(
    testimonial_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> Message:
    CatalogService(db).delete_testimonial(testimonial_id)
    return Message(detail="Testimonial deleted.")


# --------------------------------------------------------------------- orders
@router.get("/orders", response_model=list[OrderOut])
def admin_orders(
    q: str | None = None,
    status_filter: str | None = None,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    return AdminService(db).list_orders(q=q, status=status_filter)


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def admin_order(
    order_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> OrderDetailOut:
    return AdminService(db).get_order(order_id)


@router.patch("/orders/{order_id}", response_model=OrderDetailOut)
def admin_update_order(
    order_id: int,
    payload: OrderUpdate,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    return AdminService(db).update_order(order_id, payload, admin.id)


# ------------------------------------------------------------------ customers
@router.get("/customers", response_model=list[CustomerOut])
def admin_customers(
    q: str | None = None, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> list[CustomerOut]:
    return AdminService(db).list_customers(q=q)


@router.get("/customers/{user_id}", response_model=CustomerDetailOut)
def admin_customer(
    user_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> CustomerDetailOut:
    return AdminService(db).get_customer(user_id)


@router.patch("/customers/{user_id}/toggle", response_model=CustomerOut)
def admin_toggle_customer(
    user_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> CustomerOut:
    return AdminService(db).toggle_customer(user_id)


# ------------------------------------------------------------------- payments
@router.get("/payments", response_model=list[PaymentSummaryOut])
def admin_payments(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> list[PaymentSummaryOut]:
    return AdminService(db).list_payments()


# ------------------------------------------------------------------- messages
@router.get("/messages", response_model=list[ContactMessageOut])
def admin_messages(
    status_filter: str | None = None,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> list[ContactMessageOut]:
    return AdminService(db).list_messages(status=status_filter)


@router.patch("/messages/{message_id}", response_model=ContactMessageOut)
def admin_update_message(
    message_id: int,
    payload: dict,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> ContactMessageOut:
    return AdminService(db).update_message(message_id, str(payload.get("status", "")))


@router.delete("/messages/{message_id}", response_model=Message)
def admin_delete_message(
    message_id: int, admin: Admin = admin_required, db: Session = Depends(get_db)
) -> Message:
    AdminService(db).delete_message(message_id)
    return Message(detail="Message deleted.")


# ------------------------------------------------------------------- settings
@router.get("/settings", response_model=SettingsOut)
def admin_settings(
    admin: Admin = admin_required, db: Session = Depends(get_db)
) -> SettingsOut:
    return SettingsOut(**CatalogService(db).settings())


@router.put("/settings", response_model=SettingsOut)
def admin_update_settings(
    payload: SettingsUpdate,
    admin: Admin = admin_required,
    db: Session = Depends(get_db),
) -> SettingsOut:
    return SettingsOut(
        **CatalogService(db).update_settings(payload.model_dump(exclude_unset=True))
    )


# -------------------------------------------------------------------- uploads
@router.post("/uploads")
async def admin_upload(
    file: UploadFile = File(...), admin: Admin = admin_required
) -> dict[str, str]:
    return await UploadService().save(file)
