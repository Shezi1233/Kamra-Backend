from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def unique_slug(db: Session, model, value: str, *, exclude_id: int | None = None) -> str:
    base = slugify(value) or str(model.__tablename__).rstrip("s")
    candidate = base
    counter = 1
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.scalar(stmt) is None:
            return candidate
        counter += 1
        candidate = f"{base}-{counter}"
