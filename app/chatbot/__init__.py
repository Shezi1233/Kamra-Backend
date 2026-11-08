"""Isolated RAG chatbot module.

This package owns its own database (CHATBOT_DATABASE_URL) and never writes to
the website's main database. The main database is only read through the
existing repositories/services, and cart operations go through CartService.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
