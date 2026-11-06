from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.middleware.cors import add_cors, register_routes
from app.middleware.security_headers import SecurityHeadersMiddleware


def _upload_directory() -> Path:
    directory = Path(settings.upload_dir)
    if not directory.is_absolute():
        directory = Path(__file__).resolve().parents[1] / directory
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(SecurityHeadersMiddleware)
    add_cors(app)
    register_routes(app)

    if settings.upload_storage == "local":
        app.mount("/uploads", StaticFiles(directory=str(_upload_directory())), name="uploads")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
