"""Unit tests for digest assembly and HTML/JSON rendering."""

import json
import re

from sift import render, theme
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


def test_render_html_neutralizes_javascript_url_in_links(tmp_path):
    # Defense-in-depth: even if a hostile URL bypasses fetch, render must not
    # emit a javascript: href into the published/emailed HTML.
    clusters = [[Item("Evil", "javascript:alert(document.cookie)", "Feed", None, "")]]
    digest = render.build_digest("2026-26", [story("Evil", 7, [0])], clusters)
    out = tmp_path / "d.html"

    render.render_html(digest, out)
    html = out.read_text(encoding="utf-8")

    assert "javascript:alert" not in html
    assert 'href="#"' in html


def test_digest_html_has_static_image_og_card(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("Headline", 7, [0])], clusters)
    out = tmp_path / "2026-26.html"

    render.render_html(digest, out, site_url="https://x.test/sift/", cost_usd=0.12)
    html = out.read_text(encoding="utf-8")

    assert 'property="og:image" content="https://x.test/sift/digests/2026-26.png"' in html
    assert 'property="og:image:width" content="1200"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert 'property="og:url" content="https://x.test/sift/digests/2026-26.html"' in html


def test_digest_is_self_contained_no_web_fonts(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("Headline", 7, [0])], clusters)
    out = tmp_path / "d.html"

    render.render_html(digest, out)

    html = out.read_text(encoding="utf-8")
    assert "googleapis" not in html  # no external web fonts
    assert "<link rel=\"stylesheet\"" not in html  # no external CSS


def test_digest_shows_source_domain_chip(tmp_path):
    clusters = [[Item("A", "https://www.latent.space/p/x", "Latent.Space", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 6, [0])], clusters)
    out = tmp_path / "d.html"

    render.render_html(digest, out, site_url="https://x.test/sift/")

    assert "latent.space" in out.read_text(encoding="utf-8")


def test_digest_metrics_strip_shows_cost(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 6, [0])], clusters, cost_usd=0.12)
    out = tmp_path / "d.html"

    render.render_html(digest, out)
    html = out.read_text(encoding="utf-8")

    assert "$0.12" in html
    assert "1 stories" in html or "<b>1</b> stories" in html


def test_render_cost_arg_overrides_stored_cost(tmp_path):
    # On a same-week re-render the threaded (accumulated) cost must win over the
    # value baked into the stored JSON.
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 6, [0])], clusters, cost_usd=0.01)
    out = tmp_path / "d.html"

    render.render_html(digest, out, cost_usd=0.42)

    assert "$0.42" in out.read_text(encoding="utf-8")


def test_render_og_image_override_for_fallback(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 6, [0])], clusters)
    out = tmp_path / "d.html"

    render.render_html(
        digest, out, site_url="https://x.test/sift/",
        og_image="https://x.test/sift/assets/og.png",
    )

    assert 'property="og:image" content="https://x.test/sift/assets/og.png"' in out.read_text(
        encoding="utf-8"
    )


def test_digest_has_single_h1(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 6, [0])], clusters)
    out = tmp_path / "d.html"

    render.render_html(digest, out)

    assert out.read_text(encoding="utf-8").count("<h1") == 1  # a11y: one top-level heading


def test_render_json_roundtrips(tmp_path):
    clusters = [[Item("A", "https://a", "Feed A", None, "")]]
    digest = render.build_digest("2026-26", [story("X", 5, [0])], clusters)
    out = tmp_path / "d.json"

    render.render_json(digest, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))

    assert loaded["week"] == "2026-26"
    assert loaded["stories"][0]["title"] == "X"


# --- the 3D redesign ---------------------------------------------------------


def _story(**overrides):
    story = {
        "title": "A headline",
        "category": "tooling",
        "score": 7,
        "rationale": "why it matters",
        "summary": "what happened",
        "needs_verification": False,
        "links": [{"url": "https://example.com/a", "source": "Example"}],
    }
    story.update(overrides)
    return story


def test_digest_is_self_contained(tmp_path):
    """No external stylesheet, script or font: the digest must render the same
    offline and inside an email client."""
    path = tmp_path / "d.html"

    render.render_html({"week": "2026-26", "stories": [_story()]}, path)

    html = path.read_text(encoding="utf-8")
    assert "<link rel=\"stylesheet\"" not in html
    assert "fonts.googleapis.com" not in html
    assert "<script" not in html


def test_digest_uses_the_shared_palette(tmp_path):
    path = tmp_path / "d.html"

    render.render_html({"week": "2026-26", "stories": [_story()]}, path)

    html = path.read_text(encoding="utf-8")
    assert f"--accent: {render._PALETTE.accent};" in html


def test_lane_headers_carry_a_category_glyph_and_a_count(tmp_path):
    path = tmp_path / "d.html"
    stories = [_story(), _story(title="Second")]

    render.render_html({"week": "2026-26", "stories": stories}, path)

    html = path.read_text(encoding="utf-8")
    assert 'class="lane"' in html or "lane" in html
    assert "2 stories" in html
    assert 'aria-label="tooling category"' in html


def test_a_single_story_lane_is_not_pluralised(tmp_path):
    path = tmp_path / "d.html"

    render.render_html({"week": "2026-26", "stories": [_story()]}, path)

    assert "1 story" in path.read_text(encoding="utf-8")


def test_repeated_source_domains_collapse_into_one_counted_chip(tmp_path):
    """Five posts from one domain used to render five identical chips."""
    path = tmp_path / "d.html"
    links = [
        {"url": f"https://nitter.net/user{i}/status/{i}", "source": "X"} for i in range(5)
    ]

    render.render_html({"week": "2026-26", "stories": [_story(links=links)]}, path)

    html = path.read_text(encoding="utf-8")
    assert html.count('class="chip"') == 1
    assert "&times;5" in html


def test_distinct_domains_each_get_their_own_chip(tmp_path):
    path = tmp_path / "d.html"
    links = [
        {"url": "https://semgrep.dev/blog/x", "source": "A"},
        {"url": "https://interconnects.ai/p/y", "source": "B"},
    ]

    render.render_html({"week": "2026-26", "stories": [_story(links=links)]}, path)

    html = path.read_text(encoding="utf-8")
    assert html.count('class="chip"') == 2
    assert "&times;" not in html  # no count when every domain is distinct


def test_the_glance_legend_uses_the_same_glyphs_as_the_lanes(tmp_path):
    path = tmp_path / "d.html"
    stories = [_story(), _story(category="infra", title="Infra story")]

    render.render_html({"week": "2026-26", "stories": stories}, path)

    html = path.read_text(encoding="utf-8")
    assert html.count('aria-label="tooling category"') >= 2  # legend + lane
    assert html.count('aria-label="infra category"') >= 2


def test_the_favicon_is_an_inline_data_uri(tmp_path):
    path = tmp_path / "d.html"

    render.render_html({"week": "2026-26", "stories": [_story()]}, path)

    html = path.read_text(encoding="utf-8")
    assert 'href="data:image/svg+xml,' in html


def test_digest_ships_both_themes_inline(tmp_path):
    """The digest is self-contained, so it carries its own light theme rather
    than linking the site stylesheet."""
    path = tmp_path / "d.html"

    render.render_html({"week": "2026-26", "stories": [_story()]}, path)

    html = path.read_text(encoding="utf-8")
    light = theme.light_palette(render._PALETTE)
    assert "@media (prefers-color-scheme: light)" in html
    assert f"--bg: {light.bg};" in html
    assert "<link rel=\"stylesheet\"" not in html


def test_digest_iso_variables_all_resolve(tmp_path):
    path = tmp_path / "d.html"
    stories = [_story(), _story(category="infra", title="Infra")]

    render.render_html({"week": "2026-26", "stories": stories}, path)

    html = path.read_text(encoding="utf-8")
    for name in sorted(set(re.findall(r"var\((--iso-[a-z0-9-]+)", html))):
        assert f"{name}:" in html, f"{name} referenced but not defined in the digest"
