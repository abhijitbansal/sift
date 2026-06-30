"""Shared ISO-week → date helpers (week id 'YYYY-WW'). Single source of truth
for the week-id math used by both the site archive and the digest renderer."""

from __future__ import annotations

from datetime import date, timedelta


def week_end(week: str) -> date | None:
    """The Sunday that ISO week id 'YYYY-WW' ends on, or None if unparseable."""
    try:
        year_s, week_s = week.split("-")
        return date.fromisocalendar(int(year_s), int(week_s), 7)
    except (ValueError, TypeError):
        return None


def week_range(week: str) -> str:
    """Human label for an ISO week id 'YYYY-WW', e.g. 'Jun 22–28, 2026'.
    Empty string if the week id is unparseable."""
    end = week_end(week)
    if end is None:
        return ""
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}, {end.year}"
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"
