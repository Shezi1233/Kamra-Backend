from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.catalog import (
    CategoryOut,
    PortfolioOut,
    ServiceImageOut,
    ServiceOut,
    SettingsOut,
    TestimonialOut,
)
from app.schemas.common import Paginated
from app.services.catalog_service import CatalogService

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    active_only: bool = True, db: Session = Depends(get_db)
) -> list[CategoryOut]:
    return CatalogService(db).list_categories(active_only=active_only)


@router.get("/services", response_model=Paginated[ServiceOut])
def list_services(
    q: str | None = None,
    category: str | None = None,
    sort: str = Query(default="featured", pattern="^(featured|title|newest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=9, ge=1, le=100),
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> Paginated[ServiceOut]:
    service = CatalogService(db)
    total = service.count_services(
        active_only=active_only, q=q, category_slug=category
    )
    items = service.list_services(
        active_only=active_only,
        q=q,
        category_slug=category,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Paginated[ServiceOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, ceil(total / page_size)),
    )


@router.get("/services/search", response_model=list[ServiceOut])
def search_services(
    q: str = Query(min_length=1), limit: int = Query(default=8, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[ServiceOut]:
    return CatalogService(db).list_services(
        active_only=True, q=q, sort="featured", limit=limit
    )


@router.get("/services/{service_id_or_slug}", response_model=ServiceOut)
def get_service(service_id_or_slug: str, db: Session = Depends(get_db)) -> ServiceOut:
    return CatalogService(db).get_service(service_id_or_slug)


@router.get("/services/{service_id}/related", response_model=list[ServiceOut])
def related_services(service_id: int, db: Session = Depends(get_db)) -> list[ServiceOut]:
    return CatalogService(db).related_services(service_id)


@router.get("/services/{service_id}/images", response_model=list[ServiceImageOut])
def service_images(service_id: int, db: Session = Depends(get_db)) -> list[ServiceImageOut]:
    return [ServiceImageOut(**item) for item in CatalogService(db).service_images(service_id)]


@router.get("/portfolio", response_model=list[PortfolioOut])
def list_portfolio(
    active_only: bool = True, db: Session = Depends(get_db)
) -> list[PortfolioOut]:
    return CatalogService(db).list_portfolio(active_only=active_only)


@router.get("/testimonials", response_model=list[TestimonialOut])
def list_testimonials(
    approved_only: bool = True, db: Session = Depends(get_db)
) -> list[TestimonialOut]:
    return CatalogService(db).list_testimonials(approved_only=approved_only)


@router.get("/settings", response_model=SettingsOut)
def public_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return SettingsOut(**CatalogService(db).settings())
