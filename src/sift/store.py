"""SQLite history: seen URLs and digest records (with per-run cost)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
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

# Columns added after v1. Each is applied idempotently on connect() so existing
# databases migrate forward without losing rows.
_DIGEST_MIGRATIONS = {
    "model": "TEXT",
    "input_tokens": "INTEGER NOT NULL DEFAULT 0",
    "output_tokens": "INTEGER NOT NULL DEFAULT 0",
    "cost_usd": "REAL NOT NULL DEFAULT 0",
}


@dataclass(frozen=True)
class DigestRecord:
    week: str
    created_at: str
    item_count: int
    model: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float


def _migrate_digests(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(digests)")}
    for column, decl in _DIGEST_MIGRATIONS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE digests ADD COLUMN {column} {decl}")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    _migrate_digests(conn)
    conn.commit()
    return conn


def seen_urls(conn: sqlite3.Connection, since: str | None = None) -> set[str]:
    """URLs already recorded. Pass ``since`` (an ISO timestamp) to bound the
    query to recent rows, keeping the in-memory set and query cost flat as
    history grows; the window must exceed the freshness cutoff so an item that
    could still re-qualify as fresh is never forgotten."""
    if since is None:
        rows = conn.execute("SELECT url FROM items")
    else:
        rows = conn.execute("SELECT url FROM items WHERE first_seen >= ?", (since,))
    return {row[0] for row in rows}


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


def record_digest(
    conn: sqlite3.Connection,
    week: str,
    item_count: int,
    *,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO digests"
        " (week, created_at, item_count, model, input_tokens, output_tokens, cost_usd)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (week, now, item_count, model, input_tokens, output_tokens, cost_usd),
    )
    conn.commit()


def digest_history(conn: sqlite3.Connection) -> list[DigestRecord]:
    """All recorded digests, newest week first."""
    rows = conn.execute(
        "SELECT week, created_at, item_count, model, input_tokens, output_tokens, cost_usd"
        " FROM digests ORDER BY week DESC"
    )
    return [
        DigestRecord(
            week=row[0],
            created_at=row[1],
            item_count=row[2],
            model=row[3],
            input_tokens=row[4] or 0,
            output_tokens=row[5] or 0,
            cost_usd=row[6] or 0.0,
        )
        for row in rows
    ]
