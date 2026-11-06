from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Category, PortfolioProject, Service, Testimonial
from app.repositories.catalog import CatalogRepository
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
    TestimonialCreate,
    TestimonialOut,
    TestimonialUpdate,
)


def service_out(service: Service) -> ServiceOut:
    data = ServiceOut.model_validate(service)
    if service.category is not None:
        data.category_name = service.category.name
        data.category_slug = service.category.slug
    return data


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CatalogRepository(db)

    # ------------------------------------------------------------------ categories
    def list_categories(self, *, active_only: bool = False) -> list[CategoryOut]:
        counts = self.repo.service_counts()
        items = []
        for category in self.repo.list_categories(active_only=active_only):
            data = CategoryOut.model_validate(category)
            data.service_count = counts.get(category.id, 0)
            items.append(data)
        return items

    def create_category(self, payload: CategoryCreate) -> CategoryOut:
        try:
            category = self.repo.create_category(payload)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with that name already exists.",
            ) from exc
        return CategoryOut.model_validate(category)

    def update_category(self, category_id: int, payload: CategoryUpdate) -> CategoryOut:
        category = self.repo.get_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found.")
        try:
            updated = self.repo.update_category(category, payload)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with that name already exists.",
            ) from exc
        return CategoryOut.model_validate(updated)

    def delete_category(self, category_id: int) -> None:
        category = self.repo.get_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found.")
        if self.repo.category_service_count(category_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete: services still use this category.",
            )
        self.repo.delete_category(category)

    # -------------------------------------------------------------------- services
    def list_services(
        self,
        *,
        active_only: bool = True,
        q: str | None = None,
        category_slug: str | None = None,
        category_id: int | None = None,
        sort: str = "featured",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ServiceOut]:
        services = self.repo.list_services(
            active_only=active_only,
            q=q,
            category_slug=category_slug,
            category_id=category_id,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return [service_out(service) for service in services]

    def count_services(
        self,
        *,
        active_only: bool = True,
        q: str | None = None,
        category_slug: str | None = None,
        category_id: int | None = None,
    ) -> int:
        return self.repo.count_services(
            active_only=active_only,
            q=q,
            category_slug=category_slug,
            category_id=category_id,
        )

    def paginate(self, **kwargs) -> tuple[list[ServiceOut], int]:
        page = int(kwargs.pop("page", 1))
        page_size = int(kwargs.pop("page_size", 9))
        total = self.count_services(**kwargs)
        items = self.list_services(
            **kwargs, limit=page_size, offset=(page - 1) * page_size
        )
        return items, total

    def get_service(self, service_id_or_slug: str) -> ServiceOut:
        service = None
        if service_id_or_slug.isdigit():
            service = self.repo.get_service(int(service_id_or_slug))
        if service is None:
            service = self.repo.get_service_by_slug(service_id_or_slug, active_only=False)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found.")
        return service_out(service)

    def related_services(self, service_id: int) -> list[ServiceOut]:
        service = self.repo.get_service(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found.")
        return [
            service_out(item)
            for item in self.repo.related_services(service.category_id, service.id)
        ]

    def service_images(self, service_id: int) -> list[dict]:
        rows = self.repo.list_service_images(service_id)
        return [
            {
                "id": row.id,
                "service_id": row.service_id,
                "image_path": row.image_path,
                "sort_order": row.sort_order,
            }
            for row in rows
        ]

    def create_service(self, payload: ServiceCreate) -> ServiceOut:
        if not self.repo.get_category(payload.category_id):
            raise HTTPException(status_code=400, detail="Please choose a valid category.")
        try:
            service = self.repo.create_service(payload)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            raise HTTPException(status_code=400, detail="Could not create service.") from exc
        return service_out(self.repo.get_service(service.id) or service)

    def update_service(self, service_id: int, payload: ServiceUpdate) -> ServiceOut:
        service = self.repo.get_service(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found.")
        if payload.category_id and not self.repo.get_category(payload.category_id):
            raise HTTPException(status_code=400, detail="Please choose a valid category.")
        try:
            updated = self.repo.update_service(service, payload)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            raise HTTPException(status_code=400, detail="Could not update service.") from exc
        return service_out(self.repo.get_service(updated.id) or updated)

    def delete_service(self, service_id: int) -> dict:
        service = self.repo.get_service(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found.")
        if self.repo.service_used_in_orders(service_id):
            self.repo.deactivate_service(service)
            return {"detail": "Service is used in orders, so it was deactivated."}
        self.repo.delete_service(service)
        return {"detail": "Service deleted."}

    def search(self, q: str, limit: int = 8) -> list[dict]:
        if len(q.strip()) < 2:
            return []
        return [
            {
                "id": service.id,
                "title": service.title,
                "slug": service.slug,
                "category_name": service.category.name if service.category else None,
            }
            for service in self.repo.search_services(q.strip(), limit=limit)
        ]

    # ------------------------------------------------------------------- portfolio
    def list_portfolio(self, *, active_only: bool = False) -> list[PortfolioOut]:
        return [
            PortfolioOut.model_validate(item)
            for item in self.repo.list_portfolio(active_only=active_only)
        ]

    def get_portfolio(self, project_id: int) -> PortfolioOut:
        project = self.repo.get_portfolio(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        return PortfolioOut.model_validate(project)

    def create_portfolio(self, payload: PortfolioCreate) -> PortfolioOut:
        return PortfolioOut.model_validate(self.repo.create_portfolio(payload))

    def update_portfolio(self, project_id: int, payload: PortfolioUpdate) -> PortfolioOut:
        project = self.repo.get_portfolio(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        return PortfolioOut.model_validate(self.repo.update_portfolio(project, payload))

    def delete_portfolio(self, project_id: int) -> None:
        project = self.repo.get_portfolio(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        self.repo.delete_portfolio(project)

    # ---------------------------------------------------------------- testimonials
    def list_testimonials(self, *, approved_only: bool = False) -> list[TestimonialOut]:
        return [
            TestimonialOut.model_validate(item)
            for item in self.repo.list_testimonials(approved_only=approved_only)
        ]

    def create_testimonial(self, payload: TestimonialCreate) -> TestimonialOut:
        return TestimonialOut.model_validate(self.repo.create_testimonial(payload))

    def toggle_testimonial(self, testimonial_id: int) -> TestimonialOut:
        testimonial = self.repo.get_testimonial(testimonial_id)
        if not testimonial:
            raise HTTPException(status_code=404, detail="Testimonial not found.")
        return TestimonialOut.model_validate(self.repo.toggle_testimonial(testimonial))

    def delete_testimonial(self, testimonial_id: int) -> None:
        testimonial = self.repo.get_testimonial(testimonial_id)
        if not testimonial:
            raise HTTPException(status_code=404, detail="Testimonial not found.")
        self.repo.delete_testimonial(testimonial)

    # -------------------------------------------------------------------- settings
    def settings(self) -> dict[str, str]:
        data = self.repo.settings_map()
        return {
            "site_notice": data.get("site_notice", ""),
            "support_email": data.get("support_email", "smith14580@gmail.com"),
        }

    def update_settings(self, values: dict[str, str | None]) -> dict[str, str]:
        for key in ("site_notice", "support_email"):
            if key in values and values[key] is not None:
                self.repo.upsert_setting(key, values[key] or "")
        return self.settings()
