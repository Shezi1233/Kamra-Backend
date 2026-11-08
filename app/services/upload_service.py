from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.uploads import resolve_upload_dir

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _detect_mime(buffer: bytes) -> str | None:
    if buffer[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if buffer[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if buffer[:4] == b"RIFF" and buffer[8:12] == b"WEBP":
        return "image/webp"
    return None


class UploadService:
    async def save(self, file: UploadFile) -> dict[str, str]:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided.")
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPG, PNG and WebP files are allowed.",
            )
        buffer = await file.read()
        if not buffer:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        if len(buffer) > settings.upload_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File is larger than 2 MB.",
            )
        if not _detect_mime(buffer):
            raise HTTPException(status_code=400, detail="File is not a valid image.")

        name = f"{secrets.token_hex(12)}{extension}"
        if settings.upload_storage == "s3":
            url = self._save_s3(name, buffer, _detect_mime(buffer) or "application/octet-stream")
            return {"name": name, "url": url}

        directory = resolve_upload_dir()
        if directory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload storage is not available on this deployment.",
            )
        destination = directory / name
        try:
            destination.write_bytes(buffer)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload storage is not writable on this deployment.",
            ) from exc
        url = f"{settings.app_url.rstrip('/')}/uploads/{name}"
        return {"name": name, "url": url}

    def _save_s3(self, name: str, buffer: bytes, content_type: str) -> str:
        if not settings.s3_bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 storage is enabled but S3_BUCKET is not configured.",
            )
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="boto3 is required for S3 storage.",
            ) from exc

        client = boto3.client(
            "s3",
            region_name=settings.s3_region or os.getenv("AWS_REGION"),
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=name,
            Body=buffer,
            ContentType=content_type,
            ACL="public-read",
        )
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{name}"
        region = settings.s3_region or "us-east-1"
        return f"https://{settings.s3_bucket}.s3.{region}.amazonaws.com/{name}"
