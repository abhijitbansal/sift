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
    (content / "how-it-works.md").write_text("# How\n\nThe flow.", encoding="utf-8")
    (content / "features.md").write_text("# Features\n\nThe list.", encoding="utf-8")
    (content / "sources.md").write_text("## Who to follow\n\nHandles.", encoding="utf-8")
    (content / "guide.md").write_text("# Guide page", encoding="utf-8")
    (content / "roadmap.md").write_text("# Roadmap page", encoding="utf-8")


def test_build_site_writes_all_pages_and_css(tmp_path):
    seed_content(tmp_path)

    pages = site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    docs = tmp_path / "docs"
    assert pages == 7  # 6 prose pages + the archive index
    for name in (
        "index.html", "how-it-works.html", "features.html", "sources.html",
        "guide.html", "roadmap.html",
    ):
        assert (docs / name).exists()
    assert (docs / "assets" / "sift.css").exists()
    assert (docs / "digests" / "index.html").exists()
    # The sources page lists the configured feed; the home page names it too.
    assert "F" in (docs / "sources.html").read_text(encoding="utf-8")
    assert "What Sift is watching" in (docs / "index.html").read_text(encoding="utf-8")


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


def test_build_site_writes_agent_json_api(tmp_path):
    seed_content(tmp_path)
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-26.json").write_text(json.dumps({"week": "2026-26", "stories": [{}, {}]}))
    (out / "2026-27.json").write_text(json.dumps({"week": "2026-27", "stories": [{"title": "t"}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    docs = tmp_path / "docs"
    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert manifest["latest"] == "2026-27"
    assert [d["week"] for d in manifest["digests"]] == ["2026-27", "2026-26"]
    assert manifest["digests"][0]["json"] == "2026-27.json"
    assert manifest["digests"][0]["stories"] == 1
    # latest.json mirrors the newest week's full digest
    latest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    assert latest["week"] == "2026-27"
    # llms.txt agent guide at site root
    llms = (docs / "llms.txt").read_text(encoding="utf-8")
    assert "index.json" in llms and "latest.json" in llms


def test_agent_json_does_not_treat_itself_as_a_digest_on_rebuild(tmp_path):
    seed_content(tmp_path)
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-27.json").write_text(json.dumps({"week": "2026-27", "stories": [{"title": "t"}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())  # writes index.json + latest.json
    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())  # rebuild must ignore them

    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))
    weeks = [d["week"] for d in manifest["digests"]]
    assert weeks == ["2026-27"]  # NOT ["latest", "index", "2026-27"]


def test_build_site_agent_json_empty_when_no_digests(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    out = tmp_path / "docs" / "digests"
    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert manifest["latest"] is None
    assert manifest["digests"] == []
    assert not (out / "latest.json").exists()  # no digests → no latest pointer
    assert (tmp_path / "docs" / "llms.txt").exists()  # guide still written


def test_next_issue_label_is_sunday_after_latest_week():
    # 2026-26 ends Sun Jun 28 → next digest is the following Sunday, Jul 5.
    assert site._next_issue_label("2026-26").startswith("Sunday, Jul 5")


def test_next_issue_label_blank_on_bad_week():
    assert site._next_issue_label("not-a-week") == ""


def test_home_shows_next_issue_and_agent_links(tmp_path):
    seed_content(tmp_path)
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-26.json").write_text(json.dumps({"week": "2026-26", "stories": [{}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    home = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "Next issue" in home  # expected-next-digest line in the hero


def test_missing_content_file_does_not_crash(tmp_path):
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "index.md").write_text("# Only index", encoding="utf-8")

    pages = site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    assert pages == 7
    guide = (tmp_path / "docs" / "guide.html").read_text(encoding="utf-8")
    assert "missing" in guide.lower()
