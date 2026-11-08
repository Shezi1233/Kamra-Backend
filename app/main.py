from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

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
from app.utils.uploads import resolve_upload_dir

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ready = await asyncio.wait_for(init_chatbot_db(), timeout=5.0)
        if ready:
            logger.info("Chatbot database tables are ready.")
        else:
            logger.warning("CHATBOT_DATABASE_URL is not configured; chatbot DB skipped.")
    except asyncio.TimeoutError:
        logger.warning("Chatbot database initialization timed out; continuing.")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Chatbot database initialization failed; the rest of the API will run.",
            exc_info=True,
        )
    yield
    try:
        await asyncio.wait_for(dispose_chatbot_db(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Chatbot database disposal timed out.")
    except Exception:  # noqa: BLE001
        logger.warning("Chatbot database disposal failed.", exc_info=True)


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
        upload_directory = resolve_upload_dir()
        if upload_directory is not None:
            app.mount(
                "/uploads",
                StaticFiles(directory=str(upload_directory)),
                name="uploads",
            )
        else:
            logger.warning("Upload directory is unavailable; /uploads is not mounted.")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
