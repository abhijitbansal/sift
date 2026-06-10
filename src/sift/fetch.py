"""Fetch RSS/Atom feeds and normalize entries to a common Item schema."""

from __future__ import annotations

import calendar
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx

from sift.config import Feed

log = logging.getLogger("sift.fetch")

FETCH_TIMEOUT_SECONDS = 30.0
USER_AGENT = "sift/0.1 (personal RSS digest)"
SUMMARY_MAX_CHARS = 500

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    source: str
    published: datetime | None
    summary: str


def strip_html(text: str) -> str:
    """Remove tags, unescape entities, collapse whitespace."""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def parse_entry(entry: dict, source: str) -> Item | None:
    """Normalize one feedparser entry; None if it lacks a title or link."""
    title = strip_html(str(entry.get("title") or ""))
    url = str(entry.get("link") or "").strip()
    if not title or not url:
        return None

    published = None
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            published = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            break

    summary = strip_html(str(entry.get("summary") or ""))[:SUMMARY_MAX_CHARS]
    return Item(title=title, url=url, source=source, published=published, summary=summary)


def fetch_feed(client: httpx.Client, feed: Feed) -> list[Item]:
    response = client.get(feed.url)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    return [item for entry in parsed.entries if (item := parse_entry(entry, feed.name))]


def fetch_all(feeds: tuple[Feed, ...]) -> list[Item]:
    """Fetch every feed; a dead feed is logged and skipped, never fatal."""
    items: list[Item] = []
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for feed in feeds:
            try:
                feed_items = fetch_feed(client, feed)
            except Exception as exc:
                log.error("Feed failed, skipping: %s (%s): %s", feed.name, feed.url, exc)
                continue
            log.info("Fetched %d items from %s", len(feed_items), feed.name)
            items.extend(feed_items)
    return items
