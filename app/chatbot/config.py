from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatbotSettings(BaseSettings):
    """Settings for the isolated chatbot stack.

    Every value is read from the backend ``.env`` file. The main website
    database (``DATABASE_URL``) is intentionally not referenced here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Isolated chatbot database (Neon Postgres).
    chatbot_database_url: str | None = None

    # Cohere embeddings + rerank.
    cohere_api_key: str | None = None
    cohere_base_url: str = "https://api.cohere.com"
    cohere_embed_model: str = "embed-multilingual-v3.0"
    cohere_rerank_model: str = "rerank-multilingual-v3.0"
    cohere_embed_batch_size: int = Field(default=48, ge=1, le=96)

    # OpenRouter (OpenAI-compatible).
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "http://localhost:3000"
    openrouter_app_name: str = "Kamora Tech Chatbot"
    openrouter_temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    openrouter_max_tokens: int = Field(default=800, ge=100, le=4000)
    openrouter_timeout_seconds: float = Field(default=60.0, ge=5.0, le=180.0)

    # Qdrant.
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "kamora_site_knowledge"
    embedding_dimension: int = Field(default=1024, ge=1)

    # Retrieval.
    retrieval_top_k: int = Field(default=10, ge=1, le=50)
    rerank_top_n: int = Field(default=4, ge=1, le=20)
    context_char_budget: int = Field(default=6000, ge=500)
    chunk_target_tokens: int = Field(default=420, ge=100, le=500)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=200)

    # Conversation.
    max_message_chars: int = Field(default=2000, ge=50, le=10000)
    history_limit: int = Field(default=18, ge=2, le=80)
    max_agent_steps: int = Field(default=5, ge=1, le=10)
    pending_action_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    # Abuse protection.
    chat_rate_limit: str = "20/minute"
    session_rate_limit: str = "30/minute"
    ingest_rate_limit: str = "2/minute"

    @property
    def chatbot_sqlalchemy_url(self) -> str:
        url = (self.chatbot_database_url or "").strip()
        if not url:
            raise RuntimeError(
                "CHATBOT_DATABASE_URL is not configured. Set it in backend/.env."
            )
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def database_configured(self) -> bool:
        return bool((self.chatbot_database_url or "").strip())

    @property
    def cohere_configured(self) -> bool:
        return bool((self.cohere_api_key or "").strip())

    @property
    def openrouter_configured(self) -> bool:
        return bool((self.openrouter_api_key or "").strip())

    @property
    def qdrant_configured(self) -> bool:
        return bool((self.qdrant_url or "").strip())


@lru_cache
def get_chatbot_settings() -> ChatbotSettings:
    return ChatbotSettings()


chatbot_settings = get_chatbot_settings()
