"""Unit tests for SQLite history: items, digests, cost columns, migration."""

import sqlite3

from sift import store
from sift.fetch import Item


def make_item(url: str) -> Item:
    return Item(title="t", url=url, source="Feed", published=None, summary="")


def test_record_and_read_seen_urls(tmp_path):
    # Arrange
    db = tmp_path / "sift.db"
    with store.connect(db) as conn:
        store.record_items(conn, [make_item("https://a"), make_item("https://b")], "2026-26")

        # Act
        seen = store.seen_urls(conn)

    # Assert
    assert seen == {"https://a", "https://b"}


def test_record_digest_persists_cost_fields(tmp_path):
    db = tmp_path / "sift.db"
    with store.connect(db) as conn:
        store.record_digest(
            conn, "2026-26", 7,
            model="claude-opus-4-8", input_tokens=1200, output_tokens=800, cost_usd=0.026,
        )

        history = store.digest_history(conn)

    assert len(history) == 1
    record = history[0]
    assert record.week == "2026-26"
    assert record.item_count == 7
    assert record.model == "claude-opus-4-8"
    assert record.input_tokens == 1200
    assert record.cost_usd == 0.026


def test_digest_history_newest_week_first(tmp_path):
    db = tmp_path / "sift.db"
    with store.connect(db) as conn:
        store.record_digest(conn, "2026-25", 3)
        store.record_digest(conn, "2026-27", 5)
        store.record_digest(conn, "2026-26", 4)

        weeks = [r.week for r in store.digest_history(conn)]

    assert weeks == ["2026-27", "2026-26", "2026-25"]


def test_record_digest_defaults_when_cost_omitted(tmp_path):
    db = tmp_path / "sift.db"
    with store.connect(db) as conn:
        store.record_digest(conn, "2026-26", 2)

        record = store.digest_history(conn)[0]

    assert record.model is None
    assert record.input_tokens == 0
    assert record.cost_usd == 0.0


def test_connect_migrates_legacy_v1_digests_table(tmp_path):
    # Arrange: a v1 database with the old three-column digests table.
    db = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db)
    legacy.executescript(
        "CREATE TABLE digests (week TEXT PRIMARY KEY, created_at TEXT NOT NULL,"
        " item_count INTEGER NOT NULL);"
    )
    legacy.execute(
        "INSERT INTO digests (week, created_at, item_count) VALUES ('2026-20', 'then', 9)"
    )
    legacy.commit()
    legacy.close()

    # Act: connecting through store should add the cost columns without dropping the row.
    with store.connect(db) as conn:
        history = store.digest_history(conn)

    # Assert
    assert len(history) == 1
    assert history[0].week == "2026-20"
    assert history[0].item_count == 9
    assert history[0].cost_usd == 0.0
