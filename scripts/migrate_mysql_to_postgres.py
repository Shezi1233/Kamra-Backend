"""One-time migration from the legacy XAMPP MySQL database to Neon PostgreSQL."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

import pymysql
import psycopg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings


MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "agency_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# Insert parents before children.
TABLE_ORDER = [
    "users",
    "admins",
    "categories",
    "services",
    "service_images",
    "portfolio_projects",
    "testimonials",
    "coupons",
    "carts",
    "cart_items",
    "orders",
    "order_items",
    "order_status_history",
    "payments",
    "contact_messages",
    "notifications",
    "settings",
    "app_sessions",
]

ID_TABLES = [
    "users",
    "admins",
    "categories",
    "services",
    "service_images",
    "portfolio_projects",
    "testimonials",
    "coupons",
    "carts",
    "cart_items",
    "orders",
    "order_items",
    "order_status_history",
    "payments",
    "contact_messages",
    "notifications",
    "settings",
]


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_columns(connection, table: str, schema: str = "public") -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [row[0] for row in cursor.fetchall()]


def mysql_columns(cursor, table: str) -> list[str]:
    cursor.execute(f"SELECT * FROM `{table}` LIMIT 0")
    return [description[0] for description in cursor.description]


def migrate_table(mysql_cursor, pg_connection, table: str, force: bool) -> tuple[int, int]:
    mysql_cursor.execute(f"SELECT * FROM `{table}`")
    rows = mysql_cursor.fetchall()
    mysql_count = len(rows)

    pg_columns = set(table_columns(pg_connection, table))
    if not rows:
        return 0, mysql_count

    source_columns = [column for column in mysql_columns(mysql_cursor, table) if column in pg_columns]
    if not source_columns:
        raise RuntimeError(f"No common columns found for {table}")

    if force:
        with pg_connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {quote(table)} CASCADE")
    else:
        with pg_connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {quote(table)}")
            existing = cursor.fetchone()[0]
            if existing:
                raise RuntimeError(
                    f"Target table {table} already contains {existing} rows. "
                    "Use --force to replace them."
                )

    column_sql = ", ".join(quote(column) for column in source_columns)
    placeholders = ", ".join(["%s"] * len(source_columns))
    insert_sql = (
        f"INSERT INTO {quote(table)} ({column_sql}) VALUES ({placeholders})"
    )
    values = [tuple(row[column] for column in source_columns) for row in rows]

    with pg_connection.cursor() as cursor:
        cursor.executemany(insert_sql, values)
    pg_connection.commit()

    with pg_connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {quote(table)}")
        postgres_count = cursor.fetchone()[0]

    return postgres_count, mysql_count


def reset_sequences(pg_connection) -> None:
    for table in ID_TABLES:
        with pg_connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, 'id'),
                    COALESCE((SELECT MAX(id) FROM {quote(table)}), 1),
                    (SELECT COUNT(*) > 0 FROM {quote(table)})
                )
                """,
                (f"public.{table}",),
            )
    pg_connection.commit()


def main() -> int:
    force = "--force" in sys.argv

    mysql_connection = pymysql.connect(**MYSQL_CONFIG)
    mysql_cursor = mysql_connection.cursor()

    pg_url = settings.sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")
    pg_connection = psycopg.connect(pg_url)

    print("MySQL source:", MYSQL_CONFIG["host"], MYSQL_CONFIG["database"])
    print("PostgreSQL target:", settings.sqlalchemy_url.split("@")[-1])

    try:
        for table in TABLE_ORDER:
            postgres_count, mysql_count = migrate_table(mysql_cursor, pg_connection, table, force)
            status = "OK" if postgres_count == mysql_count else "MISMATCH"
            print(f"{table:24s} mysql={mysql_count:6d} postgres={postgres_count:6d} {status}")

        reset_sequences(pg_connection)
        print("sequences_reset: OK")
    finally:
        mysql_cursor.close()
        mysql_connection.close()
        pg_connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
