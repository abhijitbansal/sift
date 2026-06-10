"""Unit tests for feed entry normalization."""

from datetime import datetime, timezone

import feedparser

from sift.fetch import SUMMARY_MAX_CHARS, parse_entry, strip_html

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Sample Feed</title>
<item>
  <title>Big &amp;amp; Important &lt;b&gt;News&lt;/b&gt;</title>
  <link>https://example.com/story</link>
  <pubDate>Mon, 08 Jun 2026 12:00:00 GMT</pubDate>
  <description>&lt;p&gt;A &lt;em&gt;summary&lt;/em&gt; with   markup.&lt;/p&gt;</description>
</item>
<item>
  <title>No Link Item</title>
</item>
</channel></rss>
"""


def test_strip_html_removes_tags_and_collapses_whitespace():
    assert strip_html("<p>Hello   <b>world</b></p>") == "Hello world"


def test_strip_html_unescapes_entities():
    assert strip_html("A &amp; B") == "A & B"


def test_parse_entry_normalizes_real_feed_entry():
    # Arrange
    parsed = feedparser.parse(SAMPLE_RSS)
    entry = parsed.entries[0]

    # Act
    item = parse_entry(entry, source="Sample Feed")

    # Assert
    assert item is not None
    assert item.title == "Big & Important News"
    assert item.url == "https://example.com/story"
    assert item.source == "Sample Feed"
    assert item.published == datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    assert item.summary == "A summary with markup."


def test_parse_entry_returns_none_when_link_missing():
    parsed = feedparser.parse(SAMPLE_RSS)
    entry = parsed.entries[1]

    assert parse_entry(entry, source="Sample Feed") is None


def test_parse_entry_returns_none_when_title_missing():
    assert parse_entry({"link": "https://example.com/x"}, source="Feed") is None


def test_parse_entry_handles_missing_dates():
    item = parse_entry({"title": "Undated", "link": "https://example.com/u"}, source="Feed")

    assert item is not None
    assert item.published is None


def test_parse_entry_truncates_long_summaries():
    entry = {
        "title": "Long",
        "link": "https://example.com/long",
        "summary": "x" * (SUMMARY_MAX_CHARS * 2),
    }

    item = parse_entry(entry, source="Feed")

    assert item is not None
    assert len(item.summary) == SUMMARY_MAX_CHARS
