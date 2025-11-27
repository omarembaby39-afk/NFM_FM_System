# database_pg.py – Neon PostgreSQL helper for NFM FM System

import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

# Read DB URL from Streamlit Secrets (Cloud) or fallback to config.py (Local)
try:
    DB_URL = st.secrets["DB_URL"]
except Exception:
    from config import NEON_DB_URL as DB_URL


def get_connection():
    """Return a new connection to Neon PostgreSQL."""
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("❌ Neon connection failed:", e)
        return None


def fetch_all(sql, params=None):
    """Run a SELECT statement and return list of dict rows."""
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
# ---------- Invoice helpers ----------

def get_next_invoice_number(invoice_type: str) -> str:
    """
    invoice_type: 'FM' (monthly) or 'MNT' (maintenance).
    Pattern: INV-FM-YYYY-XXX  /  INV-MNT-YYYY-XXX
    """
    import datetime

    now = datetime.datetime.now()
    year = now.year
    prefix = f"INV-{invoice_type}-{year}-"

    # Find max existing number with that prefix
    rows = fetch_all(
        "SELECT invoice_no FROM invoices "
        "WHERE invoice_type = %s AND invoice_no LIKE %s "
        "ORDER BY invoice_no DESC LIMIT 1",
        (invoice_type, prefix + "%",),
    )

    if rows:
        last_no = rows[0]["invoice_no"]
        # Last part after last dash, e.g. 007
        last_seq_str = last_no.split("-")[-1]
        try:
            last_seq = int(last_seq_str)
        except ValueError:
            last_seq = 0
    else:
        last_seq = 0

    new_seq = last_seq + 1
    return f"{prefix}{new_seq:03d}"


def record_invoice(
    invoice_no: str,
    invoice_type: str,
    client_name: str,
    contract_ref: str,
    period: str,
    total_amount: float,
) -> bool:
    """Insert an invoice header row (id used only for history)."""

    return execute(
        """
        INSERT INTO invoices
            (invoice_no, invoice_type, client_name, contract_ref, period, total_amount)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (invoice_no) DO NOTHING
        """,
        (invoice_no, invoice_type, client_name, contract_ref, period, total_amount),
    )
