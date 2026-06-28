"""Unit tests for digest assembly and HTML/JSON rendering."""

import json

from sift import render
from sift.fetch import Item


def story(title, score, cluster_ids, category="tooling", needs_verification=False):
    return {
        "cluster_ids": cluster_ids,
        "title": title,
        "category": category,
        "score": score,
        "rationale": "because",
        "summary": "One. Two.",
        "needs_verification": needs_verification,
    }


def test_build_digest_sorts_by_score_and_attaches_links():
    clusters = [
        [Item("A", "https://a", "Feed A", None, "")],
        [Item("B", "https://b", "Feed B", None, "")],
    ]
    stories = [story("low", 3, [0]), story("high", 9, [1])]

    digest = render.build_digest("2026-26", stories, clusters)

    assert [s["title"] for s in digest["stories"]] == ["high", "low"]
    assert digest["stories"][0]["links"][0]["url"] == "https://b"


def test_render_html_groups_by_category_and_has_backlink(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("Headline", 7, [0])], clusters)
    out = tmp_path / "2026-26.html"

    render.render_html(digest, out)
    html = out.read_text(encoding="utf-8")

    assert "Tooling" in html  # category label
    assert "Headline" in html
    assert 'href="index.html"' in html  # archive backlink
    assert "Week 2026-26" in html


def test_render_html_marks_needs_verification(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 5, [0], needs_verification=True)], clusters)
    out = tmp_path / "d.html"

    render.render_html(digest, out)

    assert "needs verification" in out.read_text(encoding="utf-8")


def test_build_digest_records_scanned_sources():
    from sift.fetch import FeedResult

    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    results = [
        FeedResult("Feed A", "https://a", 3, ok=True),
        FeedResult("Dead", "https://d", 0, ok=False),
    ]

    digest = render.build_digest("2026-26", [story("X", 5, [0])], clusters, results)

    assert digest["sources_scanned"][0] == {"name": "Feed A", "count": 3, "ok": True}
    assert digest["sources_scanned"][1]["ok"] is False


def test_render_html_shows_sources_scanned(tmp_path):
    from sift.fetch import FeedResult

    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    results = [
        FeedResult("Feed A", "https://a", 3, ok=True),
        FeedResult("Dead", "https://d", 0, ok=False),
    ]
    digest = render.build_digest("2026-26", [story("X", 5, [0])], clusters, results)
    out = tmp_path / "d.html"

    render.render_html(digest, out)
    html = out.read_text(encoding="utf-8")

    assert "Sources scanned" in html
    assert "Feed A" in html
    assert "dead" in html  # the dead feed is marked
    assert "1/2 live" in html


def test_render_html_omits_scanned_section_when_absent(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 5, [0])], clusters)  # no feed_results
    out = tmp_path / "d.html"

    render.render_html(digest, out)

    assert "Sources scanned" not in out.read_text(encoding="utf-8")


def test_render_json_roundtrips(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 5, [0])], clusters)
    out = tmp_path / "d.json"

    render.render_json(digest, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))

    assert loaded["week"] == "2026-26"
    assert loaded["stories"][0]["title"] == "X"
