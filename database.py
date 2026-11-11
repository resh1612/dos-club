import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pantrymate.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pantry_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name       TEXT    NOT NULL,
            category        TEXT    DEFAULT 'Other',
            quantity        REAL    DEFAULT 1,
            unit            TEXT    DEFAULT 'pcs',
            purchase_date   DATE,
            expiry_date     DATE    NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
