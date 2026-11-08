from __future__ import annotations

import logging
from typing import Any

from app.chatbot.config import chatbot_settings
from app.chatbot.rag.providers import CohereClient, ProviderError, QdrantStore

logger = logging.getLogger("app.chatbot.retriever")


def retrieve_context(query: str) -> list[dict[str, Any]]:
    """Embed the query, retrieve top-k vectors, then rerank to top-n.

    Retrieval is best-effort: any provider/network failure returns an empty
    context so the conversation can continue using tools only.
    """

    query = (query or "").strip()
    if not query:
        return []

    try:
        cohere = CohereClient()
        qdrant = QdrantStore()
        if not cohere.configured or not qdrant.configured:
            return []

        vectors = cohere.embed([query], input_type="search_query")
        if not vectors:
            return []

        hits = qdrant.search(vectors[0], limit=chatbot_settings.retrieval_top_k)
        if not hits:
            return []

        documents = [str(hit.payload.get("text") or "") for hit in hits]
        try:
            results = cohere.rerank(
                query, documents, top_n=chatbot_settings.rerank_top_n
            )
            reranked: list[dict[str, Any]] = [
                {
                    "text": documents[item["index"]],
                    "source": hits[item["index"]].payload.get("source"),
                    "title": hits[item["index"]].payload.get("title"),
                    "score": item.get("score"),
                }
                for item in results
            ]
        except Exception:  # noqa: BLE001
            logger.warning("Rerank failed; falling back to vector order.")
            reranked = [
                {
                    "text": str(hit.payload.get("text") or ""),
                    "source": hit.payload.get("source"),
                    "title": hit.payload.get("title"),
                    "score": hit.score,
                }
                for hit in hits[: chatbot_settings.rerank_top_n]
            ]

        budget = chatbot_settings.context_char_budget
        output: list[dict[str, Any]] = []
        used = 0
        for item in reranked:
            text = str(item.get("text") or "")
            if not text:
                continue
            if used + len(text) > budget and output:
                break
            output.append(item)
            used += len(text)
        return output
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "RAG retrieval failed (%s); continuing without context.",
            type(exc).__name__,
        )
        return []
