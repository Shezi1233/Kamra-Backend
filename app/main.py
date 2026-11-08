from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.chatbot.db import dispose_chatbot_db, init_chatbot_db
from app.chatbot.rate_limit import limiter
from app.chatbot.router import router as chatbot_router
from app.core.config import settings
from app.middleware.cors import add_cors, register_routes
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ready = await init_chatbot_db()
        if ready:
            logger.info("Chatbot database tables are ready.")
        else:
            logger.warning("CHATBOT_DATABASE_URL is not configured; chatbot DB skipped.")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Chatbot database initialization failed; the rest of the API will run.",
            exc_info=True,
        )
    yield
    try:
        await dispose_chatbot_db()
    except Exception:  # noqa: BLE001
        logger.warning("Chatbot database disposal failed.", exc_info=True)


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
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(SecurityHeadersMiddleware)
    add_cors(app)
    register_routes(app)
    app.include_router(chatbot_router)

    if settings.upload_storage == "local":
        app.mount("/uploads", StaticFiles(directory=str(_upload_directory())), name="uploads")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
