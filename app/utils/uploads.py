from __future__ import annotations

import logging
import os
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("app.utils.uploads")


def resolve_upload_dir(*, create: bool = True) -> Path | None:
    """Return a writable upload directory without crashing on read-only hosts.

    Vercel's project filesystem is read-only except for /tmp, so serverless
    deployments use /tmp/uploads. Local deployments keep using UPLOAD_DIR.
    """

    if os.getenv("VERCEL"):
        directory = Path("/tmp/uploads")
    else:
        directory = Path(settings.upload_dir)
        if not directory.is_absolute():
            directory = Path(__file__).resolve().parents[2] / directory

    if not create:
        return directory

    try:
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except OSError:
        logger.warning("Could not create upload directory %s.", directory, exc_info=True)
        if directory != Path("/tmp/uploads"):
            fallback = Path("/tmp/uploads")
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                return fallback
            except OSError:
                logger.warning(
                    "Could not create fallback upload directory %s.",
                    fallback,
                    exc_info=True,
                )
        return None
