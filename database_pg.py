# database_pg.py – Neon PostgreSQL helper for NFM FM System

import psycopg2
from psycopg2.extras import RealDictCursor
from config import NEON_DB_URL


def get_connection():
    """Return a new connection to Neon, or None on error."""
    try:
        conn = psycopg2.connect(NEON_DB_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("❌ Neon connection failed:", e)
        return None


def fetch_all(sql, params=None):
    """Run SELECT and return list of dict rows."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("❌ Fetch error:", e)
        conn.close()
        return []


def execute(sql, params=None):
    """Run INSERT/UPDATE/DELETE and return True/False."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("❌ Execute error:", e)
        conn.close()
        return False
