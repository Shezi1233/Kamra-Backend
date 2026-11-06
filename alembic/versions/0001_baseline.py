"""Baseline for the existing agency_db schema.

The base tables (users, admins, categories, services, orders, ...) are owned by
the original ``database.sql``. This migration only adds the extra table required
by the API (``app_sessions``) so it is safe to run against an existing database.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-01-01

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("app_sessions"):
        return
    op.create_table(
        "app_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("idx_sessions_user", "app_sessions", ["user_id"])
    op.create_index("idx_sessions_admin", "app_sessions", ["admin_id"])
    op.create_index("idx_sessions_expiry", "app_sessions", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("app_sessions"):
        op.drop_table("app_sessions")
