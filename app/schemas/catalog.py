from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    is_active: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    service_count: int | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    is_active: int = 1


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    is_active: int | None = None


class ServiceImageOut(ORMModel):
    id: int
    service_id: int
    image_path: str
    sort_order: int


class ServiceOut(ORMModel):
    id: int
    category_id: int
    title: str
    slug: str
    short_description: str | None = None
    description: str | None = None
    price: Decimal | None = None
    delivery_estimate: str | None = None
    features: str | None = None
    technologies: str | None = None
    image: str | None = None
    is_active: int
    is_featured: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    category_name: str | None = None
    category_slug: str | None = None


class ServiceCreate(BaseModel):
    category_id: int
    title: str = Field(min_length=2, max_length=200)
    short_description: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    delivery_estimate: str | None = None
    features: str | None = None
    technologies: str | None = None
    image: str | None = None
    is_active: int = 1
    is_featured: int = 0


class ServiceUpdate(BaseModel):
    category_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    short_description: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    delivery_estimate: str | None = None
    features: str | None = None
    technologies: str | None = None
    image: str | None = None
    is_active: int | None = None
    is_featured: int | None = None


class PortfolioOut(ORMModel):
    id: int
    title: str
    category: str | None = None
    description: str | None = None
    image: str | None = None
    project_url: str | None = None
    is_featured: int
    is_active: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PortfolioCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str | None = None
    description: str | None = None
    image: str | None = None
    project_url: str | None = None
    is_featured: int = 0
    is_active: int = 1


class PortfolioUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = None
    description: str | None = None
    image: str | None = None
    project_url: str | None = None
    is_featured: int | None = None
    is_active: int | None = None


class TestimonialOut(ORMModel):
    id: int
    client_name: str
    client_role: str | None = None
    quote: str
    is_approved: int
    created_at: datetime | None = None


class TestimonialCreate(BaseModel):
    client_name: str = Field(min_length=2, max_length=150)
    client_role: str | None = None
    quote: str = Field(min_length=10, max_length=2000)
    is_approved: int = 0


class TestimonialUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=2, max_length=150)
    client_role: str | None = None
    quote: str | None = Field(default=None, min_length=10, max_length=2000)
    is_approved: int | None = None


class SearchItem(BaseModel):
    id: int
    title: str
    slug: str
    category_name: str | None = None


class SettingsOut(BaseModel):
    site_notice: str = ""
    support_email: str = ""


class SettingsUpdate(BaseModel):
    site_notice: str | None = None
    support_email: str | None = None
