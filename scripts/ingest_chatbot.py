"""Ingest public website content into Qdrant.

Run from the backend directory:

    python scripts/ingest_chatbot.py
    python scripts/ingest_chatbot.py --rebuild
    python scripts/ingest_chatbot.py --no-db --no-site
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatbot.db import dispose_chatbot_db, init_chatbot_db  # noqa: E402
from app.chatbot.rag.ingest import run_ingestion  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest website content for the chatbot.")
    parser.add_argument("--rebuild", action="store_true", help="Recreate the Qdrant collection.")
    parser.add_argument("--no-db", action="store_true", help="Skip database-backed content.")
    parser.add_argument(
        "--no-site", action="store_true", help="Skip curated FAQ/policy content."
    )
    args = parser.parse_args()

    await init_chatbot_db()
    result = await run_ingestion(
        rebuild=args.rebuild,
        include_database=not args.no_db,
        include_site_content=not args.no_site,
    )
    print(
        "Ingestion complete: "
        f"documents={result['documents']} chunks={result['chunks']} "
        f"points={result['points']} collection={result['collection']} "
        f"duration_ms={result['duration_ms']}"
    )
    await dispose_chatbot_db()


if __name__ == "__main__":
    asyncio.run(main())
