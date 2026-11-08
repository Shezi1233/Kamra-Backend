"""Create the isolated chatbot tables.

Run from the backend directory:

    python scripts/init_chatbot_db.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatbot.db import dispose_chatbot_db, init_chatbot_db  # noqa: E402


async def main() -> None:
    ready = await init_chatbot_db()
    if not ready:
        print("CHATBOT_DATABASE_URL is not configured. Nothing was created.")
        return
    print("Chatbot tables are ready.")
    await dispose_chatbot_db()


if __name__ == "__main__":
    asyncio.run(main())
