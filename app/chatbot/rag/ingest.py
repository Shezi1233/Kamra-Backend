from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.chatbot.rag.chunking import chunk_documents
from app.chatbot.rag.content import site_documents
from app.chatbot.rag.providers import (
    CohereClient,
    ProviderError,
    QdrantStore,
    deterministic_point_id,
)
from app.chatbot.config import chatbot_settings

logger = logging.getLogger("app.chatbot.ingest")


def _price_label(price: Decimal | None) -> str:
    if price is None:
        return "Request a Quote"
    try:
        return f"Rs {float(price):,.0f}"
    except (TypeError, ValueError):
        return str(price)


def _service_document(service: Any) -> dict[str, Any]:
    category_name = service.category.name if getattr(service, "category", None) else None
    category_slug = service.category.slug if getattr(service, "category", None) else None
    parts = [
        f"Service: {service.title}",
        f"Category: {category_name or 'General'}",
        f"Price: {_price_label(service.price)}",
        f"Delivery estimate: {service.delivery_estimate or 'Discussed after scope'}",
    ]
    if service.short_description:
        parts.append(f"Summary: {service.short_description}")
    if service.description:
        parts.append(f"Description: {service.description}")
    if service.features:
        parts.append(f"Features: {service.features}")
    if service.technologies:
        parts.append(f"Technologies: {service.technologies}")
    parts.append(f"Page: /services/{service.slug}")
    return {
        "source": f"service:{service.id}",
        "title": service.title,
        "text": "\n".join(parts),
        "service_id": service.id,
        "slug": service.slug,
        "url": f"/services/{service.slug}",
        "price": str(service.price) if service.price is not None else None,
        "price_label": _price_label(service.price),
        "category_name": category_name,
        "category_slug": category_slug,
    }


def collect_database_documents() -> list[dict[str, Any]]:
    """Read-only snapshot of public catalog content from the main database."""

    from app.database.connection import SessionLocal
    from app.repositories.catalog import CatalogRepository

    db: Session = SessionLocal()
    try:
        repository = CatalogRepository(db)
        documents: list[dict[str, Any]] = []

        services = repository.list_services(active_only=True, sort="title", limit=None)
        for service in services:
            documents.append(_service_document(service))

        for category in repository.list_categories(active_only=True):
            documents.append(
                {
                    "source": f"category:{category.id}",
                    "title": f"Category: {category.name}",
                    "text": (
                        f"Category: {category.name}\n"
                        f"{category.description or ''}\n"
                        f"Browse services in this category at /services?category={category.slug}"
                    ).strip(),
                    "category_id": category.id,
                }
            )

        for project in repository.list_portfolio(active_only=True):
            documents.append(
                {
                    "source": f"portfolio:{project.id}",
                    "title": f"Portfolio: {project.title}",
                    "text": (
                        f"Portfolio project: {project.title}\n"
                        f"Category: {project.category or 'General'}\n"
                        f"{project.description or ''}"
                    ).strip(),
                    "project_url": project.project_url,
                }
            )

        for testimonial in repository.list_testimonials(approved_only=True):
            documents.append(
                {
                    "source": f"testimonial:{testimonial.id}",
                    "title": "Client testimonial",
                    "text": (
                        f"Client testimonial from {testimonial.client_name}"
                        f"{' (' + testimonial.client_role + ')' if testimonial.client_role else ''}: "
                        f"{testimonial.quote}"
                    ),
                }
            )

        settings_map = repository.settings_map()
        documents.append(
            {
                "source": "site:settings",
                "title": "Website settings",
                "text": (
                    f"Support email: {settings_map.get('support_email') or 'smith14580@gmail.com'}\n"
                    f"Site notice: {settings_map.get('site_notice') or ''}"
                ).strip(),
            }
        )
        return documents
    finally:
        db.close()


def _build_documents(
    *, include_database: bool, include_site_content: bool
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    if include_site_content:
        documents.extend(site_documents())
    if include_database:
        documents.extend(collect_database_documents())
    return documents


def _ingest_sync(
    *,
    rebuild: bool,
    include_database: bool,
    include_site_content: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    cohere = CohereClient()
    qdrant = QdrantStore()

    if not cohere.configured:
        raise ProviderError("COHERE_API_KEY is not configured.")
    if not qdrant.configured:
        raise ProviderError("QDRANT_URL is not configured.")

    documents = _build_documents(
        include_database=include_database, include_site_content=include_site_content
    )
    chunks = chunk_documents(
        documents,
        target_tokens=chatbot_settings.chunk_target_tokens,
        overlap_tokens=chatbot_settings.chunk_overlap_tokens,
    )
    if not chunks:
        raise ProviderError("No content was available to ingest.")

    qdrant.ensure_collection(recreate=rebuild)

    # Embed everything in one batched pass, then group by source. This keeps
    # provider calls (and cost) low even when the catalog is large.
    vectors = cohere.embed(
        [chunk["text"] for chunk in chunks], input_type="search_document"
    )
    if len(vectors) != len(chunks):
        raise ProviderError("Embedding count mismatch during ingestion.")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk, vector in zip(chunks, vectors, strict=False):
        source = str(chunk["source"])
        grouped.setdefault(source, []).append({**chunk, "_vector": vector})

    written = 0
    for source, source_chunks in grouped.items():
        points = []
        for chunk in source_chunks:
            points.append(
                {
                    "id": deterministic_point_id(
                        source, int(chunk.get("chunk_index", 0)), chunk["text"]
                    ),
                    "vector": chunk["_vector"],
                    "payload": {
                        "text": chunk["text"],
                        "source": source,
                        "title": chunk["title"],
                        "chunk_index": chunk.get("chunk_index", 0),
                        "metadata": chunk.get("metadata", {}),
                    },
                }
            )
        if not rebuild:
            qdrant.delete_by_source(source)
        written += qdrant.upsert(points)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "collection": qdrant.collection,
        "documents": len(documents),
        "chunks": len(chunks),
        "points": written,
        "duration_ms": duration_ms,
    }


async def run_ingestion(
    *,
    rebuild: bool = False,
    include_database: bool = True,
    include_site_content: bool = True,
) -> dict[str, Any]:
    """Ingest public website content into Qdrant and record a log row."""

    from app.chatbot.db import get_session_factory
    from app.chatbot.models import IngestionLog

    result = await run_in_threadpool(
        _ingest_sync,
        rebuild=rebuild,
        include_database=include_database,
        include_site_content=include_site_content,
    )

    factory = get_session_factory()
    if factory is not None:
        async with factory() as session:
            session.add(
                IngestionLog(
                    status="success",
                    collection=result["collection"],
                    documents=result["documents"],
                    chunks=result["chunks"],
                    points=result["points"],
                    duration_ms=result["duration_ms"],
                )
            )
            await session.commit()
    return result


def log_failed_ingestion(error: str, *, collection: str | None = None) -> None:
    logger.error("Chatbot ingestion failed: %s", error)
    _ = collection
