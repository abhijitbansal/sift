"""Unit tests for static-site generation."""

import json
from datetime import date
from pathlib import Path

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


def test_prose_pages_have_static_image_og(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    idx = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'property="og:image"' in idx and "assets/og.png" in idx
    assert 'name="twitter:card" content="summary_large_image"' in idx
    assert 'property="og:url" content="https://' in idx
    assert "Skip to content" in idx  # accessibility skip link


def test_build_site_writes_static_og_png(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    assert (tmp_path / "docs" / "assets" / "og.png").exists()


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
    assert site._next_issue_label("2026-26", date(2026, 6, 29)).startswith("Sunday, Jul 5")


def test_next_issue_label_floors_at_today_when_runs_slip():
    # Latest digest is week 26 (ends Jun 28), but today is already Jul 10 — the
    # naive next Sunday (Jul 5) is in the past. Roll forward to the next future
    # Sunday so the hero never advertises a date that has already passed.
    assert site._next_issue_label("2026-26", date(2026, 7, 10)).startswith("Sunday, Jul 12")


def test_next_issue_label_includes_today_when_issue_is_due_today(tmp_path):
    # On the very Sunday the next issue is due (and no newer digest exists yet),
    # show that Sunday — it is not "past".
    assert site._next_issue_label("2026-26", date(2026, 7, 5)).startswith("Sunday, Jul 5")


def test_next_issue_label_blank_on_bad_week():
    assert site._next_issue_label("not-a-week", date(2026, 6, 29)) == ""


def test_home_shows_next_issue(tmp_path):
    seed_content(tmp_path)
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-26.json").write_text(json.dumps({"week": "2026-26", "stories": [{}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    home = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "Next issue" in home  # expected-next-digest line in the hero


def test_home_renders_agent_api_links_from_real_content(tmp_path):
    # The "For AI agents" links are prose in the real content/index.md, not code.
    # Guard them with the actual file so deleting/breaking those links fails CI;
    # stub content (used by the other tests) cannot catch that regression.
    repo_index = Path(__file__).resolve().parents[1] / "content" / "index.md"
    seed_content(tmp_path)
    (tmp_path / "content" / "index.md").write_text(
        repo_index.read_text(encoding="utf-8"), encoding="utf-8"
    )
    out = tmp_path / "docs" / "digests"
    out.mkdir(parents=True)
    (out / "2026-26.json").write_text(json.dumps({"week": "2026-26", "stories": [{}]}))

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    home = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "llms.txt" in home
    assert "digests/index.json" in home
    assert "digests/latest.json" in home


def test_missing_content_file_does_not_crash(tmp_path):
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "index.md").write_text("# Only index", encoding="utf-8")

    pages = site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    assert pages == 7
    guide = (tmp_path / "docs" / "guide.html").read_text(encoding="utf-8")
    assert "missing" in guide.lower()


# --- the 3D redesign ---------------------------------------------------------


def seed_digest(root, week="2026-26", *, title="A headline", stories=1):
    out = root / "docs" / "digests"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "week": week,
        "stories": [
            {
                "title": title if i == 0 else f"Story {i}",
                "category": "tooling",
                "score": 7,
                "rationale": "why",
                "summary": "what",
                "needs_verification": False,
                "links": [{"url": "https://example.com/a", "source": "Example"}],
            }
            for i in range(stories)
        ],
    }
    (out / f"{week}.json").write_text(json.dumps(payload), encoding="utf-8")
    return out


def test_home_hero_carries_the_generated_sieve(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    index_html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'class="hero"' in index_html
    assert "ONE CLAUDE CALL" in index_html  # the sieve's own label
    assert "not <em>noise.</em>" in index_html


def test_home_hero_renders_without_any_digests(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    index_html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'class="hero"' in index_html
    assert "Browse the archive" in index_html  # no issue yet, so no "read this week"
    assert 'class="latest"' not in index_html


def test_latest_strip_shows_live_numbers_once_an_issue_exists(tmp_path):
    seed_content(tmp_path)
    seed_digest(tmp_path, stories=3)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    index_html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'class="latest"' in index_html
    assert "Week 2026-26" in index_html
    assert ">3<" in index_html  # the story count


def test_every_page_links_the_newest_issue_from_the_header(tmp_path):
    seed_content(tmp_path)
    seed_digest(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    for name in ("index.html", "guide.html", "roadmap.html"):
        page = (tmp_path / "docs" / name).read_text(encoding="utf-8")
        assert "Read Week 2026-26" in page


def test_pipeline_marker_becomes_generated_stage_graphics(tmp_path):
    seed_content(tmp_path)
    (tmp_path / "content" / "how-it-works.md").write_text(
        "# How\n\n<!--sift:pipeline-->\n", encoding="utf-8"
    )

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    page = (tmp_path / "docs" / "how-it-works.html").read_text(encoding="utf-8")
    assert site.PIPELINE_MARKER not in page
    assert 'class="pipeline"' in page
    assert page.count("<svg") >= len(site.PIPELINE_STEPS)
    assert "Weight &amp; cut" in page


def test_category_glyph_marker_becomes_one_shape_per_category(tmp_path):
    seed_content(tmp_path)
    (tmp_path / "content" / "index.md").write_text(
        "# Home\n\n<!--sift:category-glyphs-->\n", encoding="utf-8"
    )

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    page = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert site.GLYPHS_MARKER not in page
    assert 'class="glyph-row"' in page
    for label in ("Models &amp; Research", "Tooling", "Infra", "Policy", "Business"):
        assert label in page


def test_an_unknown_marker_is_left_alone(tmp_path):
    seed_content(tmp_path)
    (tmp_path / "content" / "guide.md").write_text(
        "# Guide\n\n<!--sift:teleporter-->\n", encoding="utf-8"
    )

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    page = (tmp_path / "docs" / "guide.html").read_text(encoding="utf-8")
    assert "sift:teleporter" in page  # untouched rather than silently dropped


def test_archive_rows_show_the_issue_lead_headline(tmp_path):
    seed_content(tmp_path)
    seed_digest(tmp_path, title="GLM-5.2 beats Claude in cyber benchmarks")

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    archive = (tmp_path / "docs" / "digests" / "index.html").read_text(encoding="utf-8")
    assert "GLM-5.2 beats Claude in cyber benchmarks" in archive


def test_archive_advertises_the_next_issue_slot(tmp_path):
    seed_content(tmp_path)
    seed_digest(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    archive = (tmp_path / "docs" / "digests" / "index.html").read_text(encoding="utf-8")
    assert 'class="next-issue"' in archive
    assert "2026-27" in archive


def test_next_week_id_rolls_over_the_year():
    assert site._next_week_id("2026-26") == "2026-27"
    # 2026 is a 53-week ISO year, so week 52 is not the last one; 2025 is a
    # 52-week year, so its week 52 does roll into the next year.
    assert site._next_week_id("2026-52") == "2026-53"
    assert site._next_week_id("2026-53") == "2027-01"
    assert site._next_week_id("2025-52") == "2026-01"
    assert site._next_week_id("nonsense") == ""


def test_stylesheet_and_favicon_follow_the_palette(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    css = (tmp_path / "docs" / "assets" / "sift.css").read_text(encoding="utf-8")
    favicon = (tmp_path / "docs" / "assets" / "favicon.svg").read_text(encoding="utf-8")
    manifest = (tmp_path / "docs" / "site.webmanifest").read_text(encoding="utf-8")
    accent = site._PALETTE.accent
    assert f"--accent: {accent};" in css
    assert accent in favicon
    assert accent in manifest


def test_pages_declare_the_palette_theme_color(tmp_path):
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    index_html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert f'name="theme-color" content="{site._PALETTE.accent}"' in index_html


def test_no_stale_terracotta_hexes_remain_in_generated_css(tmp_path):
    """The old palette was hardcoded in several places; the rewrite must not
    leave any of it behind when a different palette is selected."""
    seed_content(tmp_path)

    site.build_site(tmp_path, tmp_path / "sift.db", make_cfg())

    css = (tmp_path / "docs" / "assets" / "sift.css").read_text(encoding="utf-8")
    if site._PALETTE.name != "ember":
        assert "#b4542e" not in css
        assert "#f7f3ea" not in css
