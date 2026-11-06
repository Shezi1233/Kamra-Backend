from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Kamora Tech API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str | None = None
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "agency_db"
    db_user: str = "postgres"
    db_password: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle: int = 280

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"
    app_url: str = "http://localhost:8000"

    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str | None = None
    session_days: int = 30

    upload_storage: Literal["local", "s3"] = "local"
    upload_dir: str = "uploads"
    upload_max_bytes: int = 2 * 1024 * 1024

    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_public_base_url: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            url = self.database_url.strip()
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            if url.startswith("postgresql://") and "+psycopg" not in url:
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        password = self.db_password or ""
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?sslmode=require"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
