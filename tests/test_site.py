"""Unit tests for static-site generation."""

import json

from sift import site
from sift.config import Config, Feed


def make_cfg():
    return Config(
        feeds=(Feed("F", "https://f", None, 1.0),),
        model="m",
        max_items_per_digest=10,
        interest_profile="x",
    )


def seed_content(root):
    content = root / "content"
    content.mkdir(parents=True)
    (content / "index.md").write_text("# Hello\n\nWorld paragraph.", encoding="utf-8")
    (content / "guide.md").write_text("# Guide page", encoding="utf-8")
    (content / "roadmap.md").write_text("# Roadmap page", encoding="utf-8")


def test_build_site_writes_all_pages_and_css(tmp_path):
    seed_content(tmp_path)

    pages = site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    docs = tmp_path / "docs"
    assert pages == 4
    for name in ("index.html", "guide.html", "roadmap.html"):
        assert (docs / name).exists()
    assert (docs / "assets" / "sift.css").exists()
    assert (docs / "digests" / "index.html").exists()


def test_prose_markdown_is_rendered(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    index_html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Hello</h1>" in index_html
    assert "World paragraph." in index_html


def test_archive_lists_digests_newest_first(tmp_path):
    seed_content(tmp_path)
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-26.json").write_text(json.dumps({"week": "2026-26", "stories": [{}, {}]}))
    (out / "2026-27.json").write_text(json.dumps({"week": "2026-27", "stories": [{}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    archive = (out / "index.html").read_text(encoding="utf-8")
    assert "Week 2026-26" in archive
    assert "Week 2026-27" in archive
    assert archive.index("2026-27") < archive.index("2026-26")


def test_archive_empty_state(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    archive = (tmp_path / "docs" / "digests" / "index.html").read_text(encoding="utf-8")
    assert "No digests yet" in archive


def test_missing_content_file_does_not_crash(tmp_path):
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "index.md").write_text("# Only index", encoding="utf-8")

    pages = site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    assert pages == 4
    guide = (tmp_path / "docs" / "guide.html").read_text(encoding="utf-8")
    assert "missing" in guide.lower()
