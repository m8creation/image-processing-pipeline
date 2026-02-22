"""
Database module — SQLite via Python's built-in sqlite3.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "images.db")


def get_db():
    """Return a connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                image_id     TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'processing',
                processed_at TEXT,
                width        INTEGER,
                height       INTEGER,
                format       TEXT,
                size_bytes   INTEGER,
                file_datetime TEXT,
                caption      TEXT,
                exif_data    TEXT,
                error        TEXT,
                processing_time_seconds REAL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
        logger.info("Database schema ready.")
    finally:
        conn.close()
