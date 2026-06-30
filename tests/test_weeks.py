"""Unit tests for shared ISO-week → date helpers."""

from datetime import date

from sift.weeks import week_end, week_range


def test_week_end_is_iso_sunday():
    assert week_end("2026-26") == date(2026, 6, 28)


def test_week_end_none_when_unparseable():
    assert week_end("nope") is None
    assert week_end("2026-99") is None
    assert week_end("") is None


def test_week_range_same_month():
    assert week_range("2026-26") == "Jun 22–28, 2026"


def test_week_range_cross_month():
    # ISO week 2026-05 spans late Jan into Feb — a cross-month label.
    label = week_range("2026-05")
    assert "–" in label or " – " in label
    assert "2026" in label


def test_week_range_empty_on_bad_week():
    assert week_range("bad") == ""
