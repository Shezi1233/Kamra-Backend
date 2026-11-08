from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.chatbot.config import chatbot_settings

logger = logging.getLogger("app.chatbot.providers")


class ProviderError(RuntimeError):
    """Raised when an external provider rejects or fails a request."""


class CohereClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = (api_key or chatbot_settings.cohere_api_key or "").strip()
        self.base_url = (base_url or chatbot_settings.cohere_base_url).rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("Cohere is not configured.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not texts:
            return []
        if not self.configured:
            raise ProviderError("Cohere is not configured.")

        vectors: list[list[float]] = []
        batch_size = chatbot_settings.cohere_embed_batch_size
        with httpx.Client(timeout=self.timeout) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                response = client.post(
                    f"{self.base_url}/v1/embed",
                    headers=self._headers(),
                    json={
                        "texts": batch,
                        "model": chatbot_settings.cohere_embed_model,
                        "input_type": input_type,
                        "embedding_types": ["float"],
                        "truncate": "END",
                    },
                )
                if response.status_code != 200:
                    raise ProviderError(
                        f"Cohere embed failed with status {response.status_code}."
                    )
                data = response.json()
                embeddings = data.get("embeddings")
                if isinstance(embeddings, dict):
                    embeddings = embeddings.get("float")
                if not isinstance(embeddings, list):
                    raise ProviderError("Cohere embed returned an unexpected payload.")
                vectors.extend(embeddings)
        return vectors

    def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        if not query or not documents:
            return []
        if not self.configured:
            raise ProviderError("Cohere is not configured.")

        response = httpx.post(
            f"{self.base_url}/v1/rerank",
            headers=self._headers(),
            timeout=self.timeout,
            json={
                "model": chatbot_settings.cohere_rerank_model,
                "query": query,
                "documents": documents,
                "top_n": top_n or chatbot_settings.rerank_top_n,
            },
        )
        if response.status_code != 200:
            raise ProviderError(
                f"Cohere rerank failed with status {response.status_code}."
            )
        data = response.json()
        results = data.get("results")
        if not isinstance(results, list):
            return []
        output: list[dict[str, Any]] = []
        for item in results:
            try:
                index = int(item["index"])
                score = float(item.get("relevance_score", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= index < len(documents):
                output.append(
                    {"index": index, "score": score, "text": documents[index]}
                )
        return output


@dataclass
class QdrantHit:
    id: str
    score: float
    payload: dict[str, Any]


class QdrantStore:
    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.url = (url or chatbot_settings.qdrant_url or "").rstrip("/")
        self.api_key = (api_key or chatbot_settings.qdrant_api_key or "").strip()
        self.collection = collection or chatbot_settings.qdrant_collection
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def _client(self) -> httpx.Client:
        if not self.configured:
            raise ProviderError("Qdrant is not configured.")
        return httpx.Client(timeout=self.timeout, headers=self._headers())

    def collection_exists(self) -> bool:
        with self._client() as client:
            response = client.get(f"{self.url}/collections/{self.collection}")
        return response.status_code == 200

    def ensure_collection(
        self, *, dimension: int | None = None, recreate: bool = False
    ) -> None:
        dimension = dimension or chatbot_settings.embedding_dimension
        with self._client() as client:
            if recreate:
                client.delete(f"{self.url}/collections/{self.collection}")
            else:
                existing = client.get(f"{self.url}/collections/{self.collection}")
                if existing.status_code == 200:
                    return
                if existing.status_code not in (404,):
                    raise ProviderError(
                        f"Qdrant collection check failed with status "
                        f"{existing.status_code}."
                    )
            response = client.put(
                f"{self.url}/collections/{self.collection}",
                json={"vectors": {"size": dimension, "distance": "Cosine"}},
            )
            if response.status_code not in (200, 201):
                raise ProviderError(
                    f"Qdrant collection creation failed with status "
                    f"{response.status_code}."
                )

    def delete_by_source(self, source: str) -> None:
        with self._client() as client:
            response = client.post(
                f"{self.url}/collections/{self.collection}/points/delete",
                params={"wait": "true"},
                json={
                    "filter": {
                        "must": [{"key": "source", "match": {"value": source}}]
                    }
                },
            )
        if response.status_code not in (200, 202):
            raise ProviderError(
                f"Qdrant delete failed with status {response.status_code}."
            )

    def upsert(
        self, points: list[dict[str, Any]], *, batch_size: int = 64
    ) -> int:
        if not points:
            return 0
        written = 0
        with self._client() as client:
            for start in range(0, len(points), batch_size):
                batch = points[start : start + batch_size]
                response = client.put(
                    f"{self.url}/collections/{self.collection}/points",
                    params={"wait": "true"},
                    json={"points": batch},
                )
                if response.status_code not in (200, 201):
                    raise ProviderError(
                        f"Qdrant upsert failed with status {response.status_code}."
                    )
                written += len(batch)
        return written

    def search(self, vector: list[float], *, limit: int) -> list[QdrantHit]:
        with self._client() as client:
            response = client.post(
                f"{self.url}/collections/{self.collection}/points/search",
                json={
                    "vector": vector,
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                },
            )
        if response.status_code != 200:
            raise ProviderError(
                f"Qdrant search failed with status {response.status_code}."
            )
        data = response.json()
        hits: list[QdrantHit] = []
        for item in data.get("result", []) or []:
            payload = item.get("payload") or {}
            hits.append(
                QdrantHit(
                    id=str(item.get("id")),
                    score=float(item.get("score", 0.0)),
                    payload=payload,
                )
            )
        return hits

    def count(self) -> int:
        with self._client() as client:
            response = client.post(
                f"{self.url}/collections/{self.collection}/points/count",
                json={"exact": True},
            )
        if response.status_code != 200:
            return 0
        data = response.json()
        result = data.get("result") or {}
        return int(result.get("count", 0) or 0)

    def health(self) -> bool:
        try:
            return self.collection_exists()
        except Exception:  # noqa: BLE001
            logger.warning("Qdrant health check failed", exc_info=True)
            return False


def deterministic_point_id(source: str, chunk_index: int, text: str) -> str:
    seed = f"{source}|{chunk_index}|{text[:120]}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
