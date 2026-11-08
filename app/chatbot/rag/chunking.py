from __future__ import annotations

from typing import Any


def chunk_text(
    text: str,
    *,
    target_tokens: int = 420,
    overlap_tokens: int = 50,
) -> list[str]:
    """Split text into word-based chunks.

    A word is treated as roughly one token. This avoids a tokenizer dependency
    while keeping chunks in the requested 300-500 token range with overlap.
    """

    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    words = cleaned.split(" ")
    if len(words) <= target_tokens:
        return [cleaned]

    step = max(1, target_tokens - max(0, overlap_tokens))
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + target_tokens)
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step
    return chunks


def chunk_documents(
    documents: list[dict[str, Any]],
    *,
    target_tokens: int = 420,
    overlap_tokens: int = 50,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for document in documents:
        source = str(document.get("source") or "site")
        title = str(document.get("title") or "Website content")
        metadata = {
            key: value
            for key, value in document.items()
            if key not in {"text", "source", "title"} and value is not None
        }
        for index, chunk in enumerate(
            chunk_text(
                str(document.get("text") or ""),
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
        ):
            chunks.append(
                {
                    "text": chunk,
                    "source": source,
                    "title": title,
                    "chunk_index": index,
                    "metadata": metadata,
                }
            )
    return chunks
