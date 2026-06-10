"""SQLite history: seen URLs and digest records."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sift.fetch import Item

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    published TEXT,
    first_seen TEXT NOT NULL,
    digest_week TEXT
);
CREATE TABLE IF NOT EXISTS digests (
    week TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    item_count INTEGER NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def seen_urls(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT url FROM items")}


def record_items(conn: sqlite3.Connection, items: list[Item], week: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            item.url,
            item.title,
            item.source,
            item.published.isoformat() if item.published else None,
            now,
            week,
        )
        for item in items
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO items (url, title, source, published, first_seen, digest_week)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def record_digest(conn: sqlite3.Connection, week: str, item_count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO digests (week, created_at, item_count) VALUES (?, ?, ?)",
        (week, now, item_count),
    )
    conn.commit()
