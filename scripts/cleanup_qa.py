import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.database.connection import engine

with engine.connect() as conn:
    rows = conn.execute(text("SELECT id FROM users WHERE email LIKE 'qa.%@example.com'")).fetchall()
    ids = [r[0] for r in rows]
    print("qa user ids:", ids, flush=True)
    if ids:
        conn.execute(text("DELETE FROM order_status_history WHERE order_id IN (SELECT id FROM orders WHERE user_id = ANY(:ids))"), {"ids": ids})
        conn.execute(text("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE user_id = ANY(:ids))"), {"ids": ids})
        conn.execute(text("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE user_id = ANY(:ids))"), {"ids": ids})
        conn.execute(text("DELETE FROM orders WHERE user_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM cart_items WHERE cart_id IN (SELECT id FROM carts WHERE user_id = ANY(:ids))"), {"ids": ids})
        conn.execute(text("DELETE FROM carts WHERE user_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM notifications WHERE user_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM app_sessions WHERE user_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": ids})
        conn.commit()
    count = conn.execute(text("SELECT COUNT(*) FROM users WHERE email LIKE 'qa.%@example.com'")).scalar()
    print("remaining_qa_users:", count, flush=True)
