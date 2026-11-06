from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Category, PortfolioProject, Service, ServiceImage, Testimonial
from app.schemas.catalog import (
    CategoryCreate,
    CategoryUpdate,
    PortfolioCreate,
    PortfolioUpdate,
    ServiceCreate,
    ServiceUpdate,
    TestimonialCreate,
)
from app.utils.slug import unique_slug


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------------------------------------------------------- categories
    def list_categories(self, *, active_only: bool = False) -> list[Category]:
        stmt = select(Category).order_by(Category.name)
        if active_only:
            stmt = stmt.where(Category.is_active == 1)
        return list(self.db.scalars(stmt).all())

    def get_category(self, category_id: int) -> Category | None:
        return self.db.get(Category, category_id)

    def get_category_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def service_counts(self) -> dict[int, int]:
        rows = self.db.execute(
            select(Service.category_id, func.count(Service.id)).group_by(Service.category_id)
        ).all()
        return {int(category_id): int(count) for category_id, count in rows}

    def create_category(self, payload: CategoryCreate) -> Category:
        slug = unique_slug(self.db, Category, payload.name)
        category = Category(
            name=payload.name,
            slug=slug,
            description=payload.description,
            is_active=payload.is_active,
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update_category(self, category: Category, payload: CategoryUpdate) -> Category:
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] and data["name"] != category.name:
            category.slug = unique_slug(self.db, Category, data["name"], exclude_id=category.id)
        for key, value in data.items():
            setattr(category, key, value)
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete_category(self, category: Category) -> None:
        self.db.delete(category)
        self.db.commit()

    def category_service_count(self, category_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(Service.id)).where(Service.category_id == category_id)
            )
            or 0
        )

    # ------------------------------------------------------------------ services
    def _service_filters(
        self,
        *,
        active_only: bool,
        q: str | None,
        category_slug: str | None,
        category_id: int | None,
    ) -> list:
        filters = []
        if active_only:
            filters.append(Service.is_active == 1)
        if q:
            like = f"%{q}%"
            filters.append(
                or_(
                    Service.title.like(like),
                    Service.short_description.like(like),
                    Service.description.like(like),
                )
            )
        if category_slug:
            filters.append(Category.slug == category_slug)
        if category_id:
            filters.append(Service.category_id == category_id)
        return filters

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
    ) -> list[Service]:
        stmt = (
            select(Service)
            .join(Category, Category.id == Service.category_id)
            .options(joinedload(Service.category))
        )
        for condition in self._service_filters(
            active_only=active_only, q=q, category_slug=category_slug, category_id=category_id
        ):
            stmt = stmt.where(condition)
        if sort == "title":
            stmt = stmt.order_by(Service.title.asc())
        elif sort == "newest":
            stmt = stmt.order_by(Service.id.desc())
        else:
            stmt = stmt.order_by(Service.is_featured.desc(), Service.id.asc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).unique().all())

    def count_services(
        self,
        *,
        active_only: bool = True,
        q: str | None = None,
        category_slug: str | None = None,
        category_id: int | None = None,
    ) -> int:
        stmt = (
            select(func.count(Service.id))
            .select_from(Service)
            .join(Category, Category.id == Service.category_id)
        )
        for condition in self._service_filters(
            active_only=active_only, q=q, category_slug=category_slug, category_id=category_id
        ):
            stmt = stmt.where(condition)
        return int(self.db.scalar(stmt) or 0)

    def get_service(self, service_id: int) -> Service | None:
        return self.db.scalar(
            select(Service)
            .options(joinedload(Service.category))
            .where(Service.id == service_id)
        )

    def get_service_by_slug(self, slug: str, *, active_only: bool = True) -> Service | None:
        stmt = (
            select(Service)
            .options(joinedload(Service.category))
            .where(Service.slug == slug)
        )
        if active_only:
            stmt = stmt.where(Service.is_active == 1)
        return self.db.scalar(stmt)

    def related_services(self, category_id: int, exclude_id: int, limit: int = 3) -> list[Service]:
        stmt = (
            select(Service)
            .options(joinedload(Service.category))
            .where(
                Service.category_id == category_id,
                Service.id != exclude_id,
                Service.is_active == 1,
            )
            .order_by(Service.is_featured.desc(), Service.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique().all())

    def create_service(self, payload: ServiceCreate) -> Service:
        slug = unique_slug(self.db, Service, payload.title)
        service = Service(
            category_id=payload.category_id,
            title=payload.title,
            slug=slug,
            short_description=payload.short_description,
            description=payload.description,
            price=payload.price,
            delivery_estimate=payload.delivery_estimate,
            features=payload.features,
            technologies=payload.technologies,
            image=payload.image,
            is_active=payload.is_active,
            is_featured=payload.is_featured,
        )
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    def update_service(self, service: Service, payload: ServiceUpdate) -> Service:
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] and data["title"] != service.title:
            service.slug = unique_slug(self.db, Service, data["title"], exclude_id=service.id)
        for key, value in data.items():
            setattr(service, key, value)
        self.db.commit()
        self.db.refresh(service)
        return service

    def delete_service(self, service: Service) -> None:
        self.db.delete(service)
        self.db.commit()

    def service_used_in_orders(self, service_id: int) -> bool:
        from app.models import OrderItem

        total = self.db.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.service_id == service_id)
        )
        return bool(total)

    def deactivate_service(self, service: Service) -> None:
        service.is_active = 0
        self.db.commit()

    def list_service_images(self, service_id: int) -> list[ServiceImage]:
        return list(
            self.db.scalars(
                select(ServiceImage)
                .where(ServiceImage.service_id == service_id)
                .order_by(ServiceImage.sort_order)
            ).all()
        )

    def search_services(self, q: str, limit: int = 24) -> list[Service]:
        return self.list_services(active_only=True, q=q, sort="featured", limit=limit)

    # ----------------------------------------------------------------- portfolio
    def list_portfolio(self, *, active_only: bool = False) -> list[PortfolioProject]:
        stmt = select(PortfolioProject).order_by(
            PortfolioProject.is_featured.desc(), PortfolioProject.id.desc()
        )
        if active_only:
            stmt = stmt.where(PortfolioProject.is_active == 1)
        return list(self.db.scalars(stmt).all())

    def get_portfolio(self, project_id: int) -> PortfolioProject | None:
        return self.db.get(PortfolioProject, project_id)

    def create_portfolio(self, payload: PortfolioCreate) -> PortfolioProject:
        project = PortfolioProject(**payload.model_dump())
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update_portfolio(
        self, project: PortfolioProject, payload: PortfolioUpdate
    ) -> PortfolioProject:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, key, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_portfolio(self, project: PortfolioProject) -> None:
        self.db.delete(project)
        self.db.commit()

    # --------------------------------------------------------------- testimonials
    def list_testimonials(self, *, approved_only: bool = False) -> list[Testimonial]:
        stmt = select(Testimonial).order_by(Testimonial.id.desc())
        if approved_only:
            stmt = stmt.where(Testimonial.is_approved == 1)
        return list(self.db.scalars(stmt).all())

    def get_testimonial(self, testimonial_id: int) -> Testimonial | None:
        return self.db.get(Testimonial, testimonial_id)

    def create_testimonial(self, payload: TestimonialCreate) -> Testimonial:
        testimonial = Testimonial(**payload.model_dump())
        self.db.add(testimonial)
        self.db.commit()
        self.db.refresh(testimonial)
        return testimonial

    def toggle_testimonial(self, testimonial: Testimonial) -> Testimonial:
        testimonial.is_approved = 0 if testimonial.is_approved == 1 else 1
        self.db.commit()
        self.db.refresh(testimonial)
        return testimonial

    def delete_testimonial(self, testimonial: Testimonial) -> None:
        self.db.delete(testimonial)
        self.db.commit()

    # -------------------------------------------------------------------- settings
    def settings_map(self) -> dict[str, str]:
        from app.models import Setting

        rows = self.db.scalars(select(Setting)).all()
        return {row.setting_key: row.setting_value or "" for row in rows}

    def upsert_setting(self, key: str, value: str) -> None:
        from app.models import Setting

        setting = self.db.scalar(select(Setting).where(Setting.setting_key == key))
        if setting:
            setting.setting_value = value
            setting.updated_at = datetime.now()
        else:
            self.db.add(Setting(setting_key=key, setting_value=value))
        self.db.commit()
