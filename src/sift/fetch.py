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
from sift.urls import is_http_url, is_safe_fetch_target

log = logging.getLogger("sift.fetch")

FETCH_TIMEOUT_SECONDS = 30.0
USER_AGENT = "sift/0.1 (personal RSS digest)"
SUMMARY_MAX_CHARS = 500
MAX_REDIRECTS = 5


class UnsafeURLError(RuntimeError):
    """A feed URL (or one of its redirect hops) is non-http(s) or targets a
    private/internal host (SSRF guard)."""

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    source: str
    published: datetime | None
    summary: str


@dataclass(frozen=True)
class FeedResult:
    """Per-feed outcome of one scan: how many items it returned, and whether it worked."""

    name: str
    url: str
    count: int
    ok: bool


def strip_html(text: str) -> str:
    """Remove tags, unescape entities, collapse whitespace."""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def parse_entry(entry: dict, source: str) -> Item | None:
    """Normalize one feedparser entry; None if it lacks a title or link."""
    title = strip_html(str(entry.get("title") or ""))
    url = str(entry.get("link") or "").strip()
    if not title or not url:
        return None
    # Drop hostile schemes (javascript:/data:/…) at the trust boundary so they
    # never reach dedup, the ranking prompt, storage, or an HTML href.
    if not is_http_url(url):
        log.warning("Dropping item with non-http(s) link (%s): %r", source, url)
        return None

    published = None
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            published = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            break

    summary = strip_html(str(entry.get("summary") or ""))[:SUMMARY_MAX_CHARS]
    return Item(title=title, url=url, source=source, published=published, summary=summary)


def _fetch_url(client: httpx.Client, url: str) -> httpx.Response:
    """GET ``url``, manually following redirects so EVERY hop's host is
    re-validated against the SSRF allowlist. The client must be created with
    ``follow_redirects=False`` so each redirect surfaces here."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_safe_fetch_target(current):
            raise UnsafeURLError(current)
        response = client.get(current)
        if response.is_redirect and response.next_request is not None:
            current = str(response.next_request.url)
            continue
        return response
    raise UnsafeURLError(f"too many redirects starting at {url}")


def fetch_feed(client: httpx.Client, feed: Feed) -> list[Item]:
    response = _fetch_url(client, feed.url)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    return [item for entry in parsed.entries if (item := parse_entry(entry, feed.name))]


def fetch_all(feeds: tuple[Feed, ...]) -> tuple[list[Item], list[FeedResult]]:
    """Fetch every feed; a dead feed is logged and skipped, never fatal.

    Returns the flat item list and a per-feed scan result (count + ok), so the
    digest can report exactly which sources were scanned and what each returned.
    """
    items: list[Item] = []
    results: list[FeedResult] = []
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=False,  # redirects followed manually in _fetch_url (SSRF guard)
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for feed in feeds:
            try:
                feed_items = fetch_feed(client, feed)
            except Exception as exc:
                log.error("Feed failed, skipping: %s (%s): %s", feed.name, feed.url, exc)
                results.append(FeedResult(feed.name, feed.url, 0, ok=False))
                continue
            log.info("Fetched %d items from %s", len(feed_items), feed.name)
            results.append(FeedResult(feed.name, feed.url, len(feed_items), ok=True))
            items.extend(feed_items)
    return items, results
