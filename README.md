# Kamora Tech — FastAPI Backend

This directory contains the production backend for the Kamora Tech website.
It replaces all of the legacy PHP endpoints and the direct MySQL calls that were
previously made from the Next.js server code.

## Architecture

```
backend/
├── app/
│   ├── api/v1/endpoints/   # REST endpoints (auth, catalog, cart, orders, contact, admin)
│   ├── core/               # settings, security, dependencies, constants
│   ├── database/           # SQLAlchemy engine + session
│   ├── models/             # SQLAlchemy models (mirror database.sql)
│   ├── schemas/            # Pydantic request/response schemas
│   ├── repositories/       # database access layer
│   ├── services/           # business logic
│   ├── middleware/         # CORS + security headers
│   └── utils/              # cookies, slug helpers
├── alembic/                # migrations
├── scripts/create_admin.py # secure admin creation
├── tests/
├── uploads/
├── requirements.txt
└── .env.example
```

## Setup

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env    # then edit values
```

The database is PostgreSQL on Neon. Create the schema and migrate existing MySQL data:

```bash
python -m alembic upgrade head
python scripts/migrate_mysql_to_postgres.py
```

Then apply the Alembic baseline (safe on an existing database):

```bash
alembic upgrade head
```

Create the first admin:

```bash
python scripts/create_admin.py --email admin@example.com --password "a-strong-password" --name "Site Admin"
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the OpenAPI documentation.

## Production / Vercel

Use the Neon pooled `DATABASE_URL` for the application. Use the direct Neon URL
for migrations. Vercel cannot use local XAMPP MySQL.

Set at minimum:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
CORS_ORIGINS=https://your-frontend.vercel.app
FRONTEND_URL=https://your-frontend.vercel.app
SESSION_COOKIE_SECURE=true
```

For serverless execution the pool is intentionally small (`DB_POOL_SIZE`,
`DB_MAX_OVERFLOW`) and uses `pool_pre_ping` + `pool_recycle`. If your provider
offers a serverless-friendly connection string, prefer it.

## Image uploads

The default storage is local (`UPLOAD_STORAGE=local`), which is fine locally and
on a long-running server. Vercel's filesystem is ephemeral, so in production set
`UPLOAD_STORAGE=s3` and the `S3_*` variables (works with AWS S3, Cloudflare R2,
MinIO and other S3-compatible providers).

## Authentication

- Passwords are hashed with bcrypt (cost 12).
- Sessions are opaque 32-byte tokens. Only the SHA-256 hash is stored in
  `app_sessions`, so a database leak cannot be replayed.
- Browser clients receive `HttpOnly` cookies. API clients may alternatively send
  `Authorization: Bearer <token>`.
- Admin routes require an admin session; user routes require a user session.

## Legacy PHP

The PHP files in the parent directory are legacy and are **not** used by the
Next.js app or this API. They can be archived or removed once the migration is
verified. No PHP is required to run this project.
