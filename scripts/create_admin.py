from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (".env", ".env.local"):
        path = root / name
        if path.exists():
            load_dotenv(path, override=False)


def main() -> int:
    _load_env()
    try:
        from app.core.security import hash_password
        from app.database.connection import SessionLocal
        from app.models import Admin
        from sqlalchemy import select
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Install backend/requirements.txt first.")
        return 1

    parser = argparse.ArgumentParser(description="Create or update an admin account.")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "admin@kamoratech.local"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--name", default=os.getenv("ADMIN_NAME", "Site Admin"))
    args = parser.parse_args()

    password = args.password or secrets.token_urlsafe(12)
    db = SessionLocal()
    try:
        admin = db.scalar(select(Admin).where(Admin.email == args.email.lower()))
        if admin:
            admin.full_name = args.name
            admin.password_hash = hash_password(password)
            admin.is_active = 1
            db.commit()
            print(f"Updated admin: {args.email}")
        else:
            db.add(
                Admin(
                    full_name=args.name,
                    email=args.email.lower(),
                    password_hash=hash_password(password),
                    is_active=1,
                )
            )
            db.commit()
            print(f"Created admin: {args.email}")
        if not args.password:
            print(f"Generated password: {password}")
            print("Store this password now; it is not saved anywhere else.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
