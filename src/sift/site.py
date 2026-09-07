"""Generate the static GitHub Pages site under docs/.

Pages: an explainer (index), how-it-works, features, a usage guide, a roadmap
(all from content/*.md), and a digest archive with a week picker. All share
docs/assets/sift.css for one editorial visual language; the weekly digests stay
self-contained (render.py) so they also work in email and offline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from pathlib import Path

import markdown as md

from sift import card, iso, store, theme
from sift.config import Config
from sift.meta import abs_url, og_tags
from sift.urls import safe_href
from sift.weeks import week_end, week_range

log = logging.getLogger("sift.site")

TAGLINE = "A weekly dispatch of AI signal — curated for one reader"

# The palette every generated surface reads from. Swapping this one name
# restyles the site, the digests, the cover cards and the favicon together.
_PALETTE = theme.palette()

# Home-page hero copy. This is page chrome rather than prose, so it lives here
# beside the tagline instead of in content/index.md.
HERO_TITLE = "Signal,<br>not <em>noise.</em>"
HERO_DECK = (
    "A weekly AI-news digest for one reader. Sift fetches the feeds you care about, "
    "drops what you've already seen, clusters duplicates locally, then makes "
    "<strong>one</strong> Claude call to rank and summarize the week."
)

# The seven pipeline steps, drawn by sift.iso on the how-it-works page.
PIPELINE_STEPS = (
    ("fetch", "Fetch", "Pull every configured RSS/Atom feed over HTTP. A dead or slow feed is logged and skipped — it never kills the run.", "fetch.py", False),
    ("filter", "Filter", "Drop anything already seen (tracked in SQLite) or older than eight days. Most of the firehose disappears here, for free.", "cli.py · store.py", False),
    ("dedup", "Dedup", "Cluster near-identical headlines with local string similarity, so the same story from five feeds collapses into one cluster.", "dedup.py", False),
    ("rank", "Rank", "One Claude call merges clusters that still cover the same story, assigns a category, scores importance 1–10 against your interest profile, writes a two-sentence summary, and flags non-primary-source claims.", "rank.py", True),
    ("weight", "Weight & cut", "Apply per-feed trust weights and drop anything below your min_score, then keep the top N.", "filters.py", False),
    ("render", "Render", "Write a self-contained HTML digest (and JSON) into the site's archive, so it also works in email and offline.", "render.py", False),
    ("deliver", "Record, deliver, publish", "Record the run and its exact cost, optionally email the digest, and rebuild this site so the new week shows in the archive.", "store.py · deliver.py · site.py", False),
)

# Markers a content/*.md file can use to place a generated graphic.
PIPELINE_MARKER = "<!--sift:pipeline-->"
GLYPHS_MARKER = "<!--sift:category-glyphs-->"

# JSON files we generate into docs/digests/ that are NOT weekly digests, so the
# archive scanner must skip them.
_RESERVED_JSON_STEMS = {"index", "latest"}

# slug -> (nav label, page title, content filename)
PROSE_PAGES = {
    "index": ("Home", "Sift — weekly AI-news curation", "index.md"),
    "how-it-works": ("How it works", "Sift — how it works", "how-it-works.md"),
    "features": ("Features", "Sift — features", "features.md"),
    "sources": ("Sources", "Sift — sources", "sources.md"),
    "guide": ("Guide", "Sift — usage guide", "guide.md"),
    "roadmap": ("Roadmap", "Sift — roadmap", "roadmap.md"),
}

NAV = [
    ("index.html", "Home", "index"),
    ("how-it-works.html", "How it works", "how-it-works"),
    ("features.html", "Features", "features"),
    ("sources.html", "Sources", "sources"),
    ("guide.html", "Guide", "guide"),
    ("roadmap.html", "Roadmap", "roadmap"),
    ("digests/index.html", "Archive", "digests"),
]


@dataclass(frozen=True)
class ArchiveEntry:
    week: str
    range_label: str
    count: int
    cost_usd: float
    lead: str = ""  # the issue's top-ranked headline, shown in the archive list


def build_site(root: Path, db_path: Path, cfg: Config) -> int:
    """Render every site page. Returns the number of pages written."""
    docs = root / "docs"
    assets = docs / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "sift.css").write_text(_site_css(), encoding="utf-8")
    (assets / "favicon.svg").write_text(_favicon_svg(), encoding="utf-8")
    (docs / "site.webmanifest").write_text(_webmanifest(), encoding="utf-8")
    card.render_static_card(assets / "og.png")  # best-effort; static og:image + fallback

    out_dir = docs / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    history = _history_by_week(db_path)
    entries = _archive_entries(out_dir, history)
    _refresh_digests(out_dir, history, cfg)  # re-render archived digests + cover cards

    content_dir = root / "content"
    today = date.today()
    latest_week = entries[0].week if entries else None
    pages = 0
    for slug, (_, title, filename) in PROSE_PAGES.items():
        body = _render_prose(content_dir / filename)
        if slug == "index":
            body = _home_hero(entries[0] if entries else None, today) + body
            body = body + _home_sources_html(cfg)
        elif slug == "sources":
            body = _configured_feeds_html(cfg) + body
        rel = "" if slug == "index" else f"{slug}.html"
        (docs / f"{slug}.html").write_text(
            _wrap(
                title, body, prefix="", active=slug, cfg=cfg, rel=rel,
                latest_week=latest_week,
            ),
            encoding="utf-8",
        )
        pages += 1

    (out_dir / "index.html").write_text(
        _wrap(
            "Sift — digest archive", _archive_body(entries, today),
            prefix="../", active="digests", cfg=cfg, rel="digests/index.html",
            latest_week=latest_week,
        ),
        encoding="utf-8",
    )
    pages += 1
    _write_agent_json(docs, out_dir, entries, cfg)
    log.info("Built %d site pages (%d archived digests)", pages, len(entries))
    return pages


def _refresh_digests(out_dir: Path, history: dict, cfg: Config) -> None:
    """Re-render each archived digest's HTML from its committed JSON (so a theme
    or OG change reaches old issues) and write its cover card. Best-effort per
    digest: a malformed/legacy JSON is logged and skipped, never fatal."""
    from sift import render

    for json_path in out_dir.glob("*.json"):
        week = json_path.stem
        if week in _RESERVED_JSON_STEMS:
            continue
        try:
            digest = json.loads(json_path.read_text(encoding="utf-8"))
            stories = digest.get("stories", [])
            record = history.get(week)
            cost = record.cost_usd if record else None
            # Render the cover card first so the digest's og:image only points at
            # the per-issue PNG when it actually exists; otherwise fall back to the
            # committed static og.png so the unfurl image never 404s.
            card_ok = False
            if stories:
                counts: dict[str, int] = {}
                for s in stories:
                    counts[s["category"]] = counts.get(s["category"], 0) + 1
                card_ok = card.render_issue_card(
                    out_dir / f"{week}.png",
                    week=week,
                    range_label=week_range(week),
                    headline=stories[0].get("title", "Weekly AI signal"),
                    category_counts=counts,
                    story_count=len(stories),
                    feed_count=len(digest.get("sources_scanned", []) or cfg.feeds),
                )
            og_image = abs_url(
                cfg.site_url, f"digests/{week}.png" if card_ok else "assets/og.png"
            )
            render.render_html(
                digest,
                out_dir / f"{week}.html",
                site_url=cfg.site_url,
                cost_usd=cost,
                og_image=og_image,
            )
        except Exception:  # noqa: BLE001 - best-effort archive refresh
            log.warning("Could not refresh digest %s; left as-is", week, exc_info=True)


def _write_agent_json(
    docs: Path, out_dir: Path, entries: list[ArchiveEntry], cfg: Config
) -> None:
    """Machine-readable surface for AI agents: a digest index manifest, a stable
    latest.json (the newest week's full digest), and an llms.txt guide."""
    manifest = {
        "title": "Sift",
        "tagline": TAGLINE,
        "feeds_scanned": len(cfg.feeds),
        "latest": entries[0].week if entries else None,
        "digests": [
            {
                "week": e.week,
                "range": e.range_label,
                "stories": e.count,
                "cost_usd": round(e.cost_usd, 4),
                "html": f"{e.week}.html",
                "json": f"{e.week}.json",
            }
            for e in entries
        ],
    }
    (out_dir / "index.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if entries:
        latest_src = out_dir / f"{entries[0].week}.json"
        if latest_src.exists():
            (out_dir / "latest.json").write_text(
                latest_src.read_text(encoding="utf-8"), encoding="utf-8"
            )
    (docs / "llms.txt").write_text(LLMS_TXT, encoding="utf-8")


def _configured_feeds_html(cfg: Config) -> str:
    """The live list of feeds Sift scans, read from config — for the Sources page."""
    rows = []
    for feed in cfg.feeds:
        meta = []
        if feed.category_hint:
            meta.append(escape(feed.category_hint))
        if feed.weight != 1.0:
            meta.append(f"weight {feed.weight:g}")
        meta_html = f' <span class="feed-meta">{" &middot; ".join(meta)}</span>' if meta else ""
        rows.append(
            f'<li><a href="{escape(safe_href(feed.url))}">{escape(feed.name)}</a>{meta_html}</li>'
        )
    return (
        "<h1>Sources</h1>\n"
        f"<p>Sift scans these <strong>{len(cfg.feeds)}</strong> feeds every run — "
        "fetched and filtered locally, with one Claude call to rank what's left. "
        "Tune any source with a <code>weight</code> in <code>config.toml</code>.</p>\n"
        f'<ul class="feeds">\n' + "\n".join(rows) + "\n</ul>\n"
    )


def _home_sources_html(cfg: Config) -> str:
    """A compact 'what Sift is watching' block for the home page."""
    names = " &middot; ".join(escape(feed.name) for feed in cfg.feeds)
    return (
        '<section class="home-sources">\n'
        "<h2>What Sift is watching</h2>\n"
        f"<p><strong>{len(cfg.feeds)}</strong> sources scanned every week:</p>\n"
        f'<p class="feed-names">{names}</p>\n'
        '<p><a href="sources.html">Full source list &amp; who to follow on X &rarr;</a></p>\n'
        "</section>\n"
    )


def _render_prose(path: Path) -> str:
    """Markdown to HTML, with any ``<!--sift:...-->`` marker replaced by the
    graphic it names. Markers let the copy stay in content/*.md while the
    drawings stay generated."""
    if not path.exists():
        return f"<p><em>Content file missing: {escape(path.name)}</em></p>"
    html = md.markdown(
        path.read_text(encoding="utf-8"), extensions=["extra", "sane_lists"]
    )
    for marker, build in (
        (PIPELINE_MARKER, _pipeline_html),
        (GLYPHS_MARKER, _category_glyphs_html),
    ):
        if marker in html:
            html = html.replace(marker, build())
    return html


def _history_by_week(db_path: Path) -> dict[str, store.DigestRecord]:
    try:
        with store.connect(db_path) as conn:
            return {record.week: record for record in store.digest_history(conn)}
    except Exception:  # noqa: BLE001 - archive should build even without a usable db
        log.exception("Could not read digest history; archive will omit cost")
        return {}


def _archive_entries(
    out_dir: Path, history: dict[str, store.DigestRecord]
) -> list[ArchiveEntry]:
    entries = []
    for json_path in sorted(out_dir.glob("*.json"), reverse=True):
        week = json_path.stem
        if week in _RESERVED_JSON_STEMS:  # our own agent-API files, not digests
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # ValueError covers JSON + UnicodeDecodeError
            log.warning("Skipping unreadable digest json: %s", json_path)
            continue
        record = history.get(week)
        stories = data.get("stories", [])
        entries.append(
            ArchiveEntry(
                week=week,
                range_label=week_range(week),
                count=len(stories),
                cost_usd=record.cost_usd if record else 0.0,
                lead=stories[0].get("title", "") if stories else "",
            )
        )
    return entries


def _meta_line(entry: ArchiveEntry) -> str:
    bits = [f"{entry.count} stories"]
    if entry.cost_usd:
        bits.append(f"${entry.cost_usd:.2f}")
    return " &middot; ".join(bits)


def _next_issue_label(latest_week: str, today: date) -> str:
    """Human date of the next expected digest: the Sunday after the latest week's
    ending Sunday, floored at ``today`` so a slipped/missed run never advertises a
    date already in the past — it rolls forward to the next future Sunday instead.
    Empty string if the week id is unparseable."""
    ending_sunday = week_end(latest_week)
    if ending_sunday is None:
        return ""
    nxt = ending_sunday + timedelta(days=7)
    while nxt < today:  # a Sunday that has already passed → roll to the next one
        nxt += timedelta(days=7)
    return f"{nxt:%A, %b} {nxt.day}, {nxt.year}"


ARROW_SVG = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M3 8h10M9 4l4 4-4 4"></path></svg>'
)


def _home_hero(entry: ArchiveEntry | None, today: date) -> str:
    """The home page's opening: the sieve object, the pitch, and — once there is
    at least one issue — a strip of live numbers from the latest run."""
    read_cta = (
        f'<a class="btn btn-primary" href="digests/{escape(entry.week)}.html">'
        f"Read this week's issue{ARROW_SVG}</a>"
        if entry
        else '<a class="btn btn-primary" href="digests/index.html">'
        f"Browse the archive{ARROW_SVG}</a>"
    )
    return (
        '<section class="hero">\n'
        '<div class="hero-copy">\n'
        '<p class="kicker">Weekly <span class="dot">·</span> one Claude call</p>\n'
        f"<h1>{HERO_TITLE}</h1>\n"
        f'<p class="deck">{HERO_DECK}</p>\n'
        f'<div class="hero-cta">{read_cta}'
        f'<a class="btn btn-ghost" href="how-it-works.html">How it works</a></div>\n'
        "</div>\n"
        f'<div class="hero-art">{iso.hero_sieve(_PALETTE)}</div>\n'
        "</section>\n"
    ) + _latest_strip(entry, today)


def _latest_strip(entry: ArchiveEntry | None, today: date) -> str:
    if entry is None:
        return ""
    next_label = _next_issue_label(entry.week, today)
    cost = f"${entry.cost_usd:.2f}" if entry.cost_usd else "—"
    next_cell = (
        f'<div class="cell"><span class="lab">Next issue</span>'
        f'<span class="val" style="font-size:1.05rem">{escape(next_label)}</span></div>'
        if next_label
        else ""
    )
    return (
        '<section class="latest" aria-label="Latest issue">\n'
        '<div class="cell"><span class="lab">Latest issue</span>'
        f'<span class="val"><a href="digests/{escape(entry.week)}.html">Week {escape(entry.week)}</a>'
        f"<small>{escape(entry.range_label)}</small></span></div>\n"
        f'<div class="cell"><span class="lab">Stories</span><span class="val">{entry.count}</span></div>\n'
        f'<div class="cell"><span class="lab">Run cost</span><span class="val">{cost}</span></div>\n'
        f"{next_cell}\n"
        "</section>\n"
    )


def _pipeline_html() -> str:
    """The seven-step pipeline, each step drawn as an isometric block."""
    stages = []
    for index, (kind, title, blurb, module, paid) in enumerate(PIPELINE_STEPS, start=1):
        stages.append(
            f'<div class="stage{" paid" if paid else ""}">'
            f"{iso.stage_block(kind, _PALETTE)}"
            f'<span class="n">{index:02d}</span>'
            f"<h4>{escape(title)}</h4>"
            f"<p>{escape(blurb)}</p>"
            f'<span class="mod">{escape(module)}</span>'
            "</div>"
        )
    return (
        f'<div class="pipeline">{"".join(stages)}</div>\n'
        '<p class="pipeline-note"><i></i>Everything except Rank is local and free. '
        "Cost per run is recorded to the cent.</p>\n"
    )


def _category_glyphs_html() -> str:
    """The five ranked categories, each with its own isometric primitive."""
    items = "".join(
        f"<span>{iso.category_glyph(category, _PALETTE)}{escape(label)}</span>"
        for category, label in theme.CATEGORY_LABELS.items()
    )
    return f'<div class="glyph-row">{items}</div>\n'


def _archive_body(entries: list[ArchiveEntry], today: date) -> str:
    if not entries:
        return (
            "<h1>Digest archive</h1>\n"
            "<p>No digests yet. Run <code>uv run sift run</code> to generate the first one.</p>"
        )
    options = "\n".join(
        f'<option value="{escape(e.week)}.html">Week {escape(e.week)} &middot; '
        f"{escape(e.range_label)}</option>"
        for e in entries
    )
    rows = "\n".join(
        f'<li data-label="{escape((e.week + " " + e.range_label).lower())}">'
        f'<a href="{escape(e.week)}.html">'
        f'<span><span class="wk">{escape(e.week)}</span>'
        f'<span class="rng">{escape(e.range_label)}</span></span>'
        f'<span class="lead">{escape(e.lead or "")}</span>'
        f'<span class="meta">{_meta_line(e)}</span></a></li>'
        for e in entries
    )
    next_label = _next_issue_label(entries[0].week, today)
    next_html = (
        '<div class="next-issue">'
        f'<span class="wk">{escape(_next_week_id(entries[0].week))}</span>'
        f'<span class="pulse"><i></i>Next issue lands <b>{escape(next_label)}</b> — '
        "the weekly job publishes it here automatically.</span></div>\n"
        if next_label
        else ""
    )
    return (
        "<h1>Digest archive</h1>\n"
        "<p>Each week's digest is a self-contained HTML file with a JSON twin, committed to "
        "the repo and served from here. Nothing is regenerated after the fact, so an old "
        "issue reads exactly as it was sent.</p>\n"
        '<div class="archive-controls">\n'
        '<input id="archive-filter" type="search" placeholder="Filter issues…" '
        'aria-label="Filter issues">\n'
        '<select id="archive-jump" aria-label="Jump to an issue">\n'
        '<option value="">Jump to an issue…</option>\n'
        f"{options}\n</select>\n</div>\n"
        f'<ul class="archive" id="archive-list">\n{rows}\n</ul>\n'
        '<p class="archive-empty" id="archive-empty" hidden>No issues match that filter.</p>\n'
        f"{next_html}"
        f"{_ARCHIVE_JS}"
    )


def _next_week_id(week: str) -> str:
    """The ISO id of the week after ``week`` — used to label the pending slot."""
    ending = week_end(week)
    if ending is None:
        return ""
    nxt = ending + timedelta(days=7)
    iso_year, iso_week, _ = nxt.isocalendar()
    return f"{iso_year}-{iso_week:02d}"


_ARCHIVE_JS = """<script>
(function () {
  var jump = document.getElementById('archive-jump');
  if (jump) jump.addEventListener('change', function () {
    if (this.value) window.location.href = this.value;
  });
  var filter = document.getElementById('archive-filter');
  var items = [].slice.call(document.querySelectorAll('#archive-list > li'));
  var empty = document.getElementById('archive-empty');
  if (filter) filter.addEventListener('input', function () {
    var q = this.value.trim().toLowerCase();
    var shown = 0;
    items.forEach(function (li) {
      var match = li.getAttribute('data-label').indexOf(q) !== -1;
      li.hidden = !match;
      if (match) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
  });
})();
</script>
"""


def _wrap(
    title: str, body_html: str, *, prefix: str, active: str, cfg: Config, rel: str,
    latest_week: str | None = None,
) -> str:
    nav_links = "".join(
        f'<a href="{prefix}{href}"'
        + (' class="active"' if slug == active else "")
        + f">{escape(label)}</a>"
        for href, label, slug in NAV
    )
    footer_links = "".join(
        f'<a href="{prefix}{href}">{escape(label)}</a>'
        for href, label, _ in NAV
        if label != "Home"
    )
    cta = (
        f'<a class="btn btn-primary" href="{prefix}digests/{escape(latest_week)}.html">'
        f"Read Week {escape(latest_week)}{ARROW_SVG}</a>"
        if latest_week
        else ""
    )
    og = og_tags(
        title=title,
        description=TAGLINE,
        url=abs_url(cfg.site_url, rel),
        image=abs_url(cfg.site_url, "assets/og.png"),
        image_alt="Sift — a weekly dispatch of AI signal",
    )
    return _PAGE_TEMPLATE.format(
        title=escape(title),
        og=og,
        css=f"{prefix}assets/sift.css",
        favicon=f"{prefix}assets/favicon.svg",
        ico=f"{prefix}assets/favicon.ico",
        apple=f"{prefix}assets/apple-touch-icon.png",
        manifest=f"{prefix}site.webmanifest",
        theme_color=_PALETTE.accent,
        fonts=theme.GOOGLE_FONTS_HREF,
        brand=f"{prefix}index.html",
        mark=iso.mark(_PALETTE, size=32),
        nav=nav_links,
        footer_nav=footer_links,
        cta=cta,
        body=body_html,
    )


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="A weekly dispatch of AI signal — curated for one reader.">
<link rel="icon" href="{favicon}" type="image/svg+xml">
<link rel="icon" href="{ico}" sizes="32x32" type="image/x-icon">
<link rel="apple-touch-icon" href="{apple}">
<link rel="manifest" href="{manifest}">
<meta name="theme-color" content="{theme_color}">
{og}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<link rel="stylesheet" href="{css}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="page-glow" aria-hidden="true"></div>
<header class="masthead">
<div class="masthead-inner">
<a class="brand" href="{brand}">{mark}<span>Sift<b>.</b></span></a>
<nav aria-label="Primary">{nav}</nav>
{cta}
</div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
<div class="footer-inner">
<p>Sift &mdash; a weekly AI-news curation pipeline for one reader. One Claude call
per week; everything else local and free.</p>
<div class="footer-links">{footer_nav}</div>
</div>
</footer>
</body>
</html>
"""


def _favicon_svg() -> str:
    return iso.favicon(_PALETTE)


def _webmanifest() -> str:
    return json.dumps(
        {
            "name": "Sift",
            "short_name": "Sift",
            "description": "A weekly AI-news digest, curated for one reader.",
            "theme_color": _PALETTE.accent,
            "background_color": _PALETTE.bg,
            "display": "minimal-ui",
            "icons": [
                {"src": "assets/favicon.svg", "type": "image/svg+xml", "sizes": "any"},
                {"src": "assets/favicon-32.png", "type": "image/png", "sizes": "32x32"},
                {"src": "assets/favicon-16.png", "type": "image/png", "sizes": "16x16"},
                {"src": "assets/apple-touch-icon.png", "type": "image/png", "sizes": "180x180"},
            ],
        },
        indent=2,
    ) + "\n"


def _site_css() -> str:
    """The whole stylesheet, with every color coming from the palette."""
    pal = _PALETTE
    return f"""{theme.css_variables(pal)}
{theme.category_selectors(pal)}
:root {{
  --display: {theme.FONT_DISPLAY};
  --body: {theme.FONT_BODY};
  --mono: {theme.FONT_MONO};
  --line: {pal.glass_rgba(0.10)};
  --line-2: {pal.glass_rgba(0.18)};
  --surface: {pal.glass_rgba(0.045)};
  --surface-2: {pal.glass_rgba(0.08)};
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; overflow-x: hidden; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
  font: 17px/1.55 var(--body); -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility; overflow-x: hidden; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ color: var(--accent-hi); }}
::selection {{ background: var(--accent); color: var(--accent-ink); }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 4px; }}
h1, h2, h3, h4 {{ font-family: var(--display); font-optical-sizing: auto;
  text-wrap: balance; margin: 0; }}
p {{ margin: 0; text-wrap: pretty; }}
img, svg {{ max-width: 100%; }}

.skip {{ position: absolute; left: -9999px; top: 0; z-index: 90; background: var(--accent);
  color: var(--accent-ink); font-family: var(--mono); font-size: .75rem; font-weight: 500;
  padding: .7rem 1.1rem; border-radius: 0 0 10px 0; }}
.skip:focus {{ left: 0; }}

/* A single soft light source behind the top of every page. */
.page-glow {{ position: absolute; top: -300px; right: 0; width: min(56rem, 100%);
  height: 900px; border-radius: 50%; pointer-events: none; z-index: 0;
  background: radial-gradient(closest-side, {pal.accent_rgba(0.16)}, {pal.accent_rgba(0)} 100%); }}

.masthead, main, .site-footer {{ position: relative; z-index: 1; }}
.masthead-inner, main, .footer-inner {{ width: 100%; max-width: 72rem; margin: 0 auto;
  padding-left: 2rem; padding-right: 2rem; }}
.masthead-inner {{ display: flex; align-items: center; justify-content: space-between;
  gap: 1.5rem; min-height: 5rem; flex-wrap: wrap; }}
.brand {{ display: inline-flex; align-items: center; gap: .55rem; min-height: 44px;
  font-family: var(--display); font-weight: 800; font-size: 1.7rem; letter-spacing: -.03em;
  color: var(--text); font-variation-settings: "opsz" 96; }}
.brand b {{ color: var(--accent); }}
.brand svg {{ width: 2rem; height: 2rem; }}
.masthead nav {{ display: flex; flex-wrap: wrap; gap: 1.6rem; }}
.masthead nav a {{ font-family: var(--mono); font-size: .72rem; font-weight: 500;
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted); min-height: 44px;
  display: inline-flex; align-items: center; border-bottom: 1px solid transparent;
  transition: color .15s, border-color .15s; }}
.masthead nav a:hover {{ color: var(--text); }}
.masthead nav a.active {{ color: var(--text); border-bottom-color: var(--accent); }}

.btn {{ display: inline-flex; align-items: center; justify-content: center; gap: .6rem;
  min-height: 44px; padding: 0 1.15rem; border-radius: 12px; font-family: var(--body);
  font-weight: 600; font-size: .92rem; white-space: nowrap; }}
.btn svg {{ width: 1rem; height: 1rem; }}
.btn-primary {{ background: var(--accent); color: var(--accent-ink);
  box-shadow: 0 10px 30px {pal.accent_rgba(0.30)}, inset 0 1px 0 rgba(255,255,255,.25); }}
.btn-primary:hover {{ background: var(--accent-hi); color: var(--accent-ink); }}
.btn-ghost {{ background: var(--surface); color: var(--text); border: 1px solid var(--line-2); }}
.btn-ghost:hover {{ border-color: var(--accent); color: var(--text); }}

main {{ padding-top: 2rem; padding-bottom: 1rem; }}

/* Home hero */
.hero {{ display: grid; grid-template-columns: minmax(0, 1.02fr) minmax(0, .98fr);
  gap: 2.5rem; align-items: center; padding: 2rem 0 1rem; }}
.hero-copy {{ display: flex; flex-direction: column; gap: 1.6rem; max-width: 34rem; }}
.hero h1 {{ font-size: clamp(3rem, 7.5vw, 6.5rem); line-height: .92; letter-spacing: -.045em;
  font-weight: 700; font-variation-settings: "opsz" 96; }}
.hero h1 em {{ font-style: normal; color: var(--accent); }}
.hero .deck {{ font-size: 1.2rem; line-height: 1.5; color: var(--text-2); }}
.hero .deck strong {{ color: var(--text); font-weight: 600; }}
.hero-cta {{ display: flex; flex-wrap: wrap; gap: .85rem; }}
.hero-art {{ display: flex; justify-content: center; align-items: center; }}
.hero-art svg {{ width: min(100%, 40rem); height: auto;
  filter: drop-shadow(0 30px 60px rgba(0,0,0,.45)); animation: floaty 7s ease-in-out infinite alternate; }}
@keyframes floaty {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-12px); }} }}
.kicker {{ font-family: var(--mono); font-size: .75rem; font-weight: 500; letter-spacing: .16em;
  text-transform: uppercase; color: var(--muted); }}
.kicker .dot {{ color: var(--accent); }}

/* Latest-issue strip */
.latest {{ display: grid; grid-template-columns: 1.6fr repeat(3, 1fr) auto; align-items: center;
  gap: 0; padding: 1.25rem 1.6rem; margin: 1.5rem 0 0; background: var(--surface);
  border: 1px solid var(--line); border-radius: 16px;
  box-shadow: inset 0 1px 0 {pal.glass_rgba(0.08)}, 0 20px 50px rgba(0,0,0,.35); }}
.latest .cell {{ display: flex; flex-direction: column; gap: .2rem; padding: 0 1.6rem;
  border-left: 1px solid var(--line); }}
.latest .cell:first-child {{ padding-left: 0; border-left: 0; }}
.latest .cell:last-child {{ padding-right: 0; }}
.latest .lab {{ font-family: var(--mono); font-size: .68rem; letter-spacing: .14em;
  text-transform: uppercase; color: var(--muted); }}
.latest .val {{ font-family: var(--display); font-size: 1.5rem; font-weight: 600;
  letter-spacing: -.02em; color: var(--text); line-height: 1.1; }}
.latest .val small {{ font-family: var(--body); font-size: .92rem; font-weight: 400;
  color: var(--text-2); margin-left: .6rem; letter-spacing: 0; }}
.latest .live {{ display: inline-flex; align-items: center; gap: .5rem; }}
.latest .live i {{ width: .5rem; height: .5rem; border-radius: 50%; background: var(--live);
  box-shadow: 0 0 0 4px rgba(74,222,128,.15); }}

/* Prose */
main h1 {{ font-size: clamp(2.4rem, 5vw, 3.6rem); line-height: 1; letter-spacing: -.04em;
  font-weight: 700; margin: 1rem 0 1.2rem; font-variation-settings: "opsz" 96; }}
main h2 {{ font-size: clamp(1.6rem, 3vw, 2.1rem); line-height: 1.1; letter-spacing: -.03em;
  font-weight: 600; margin: 3rem 0 1rem; }}
main h3 {{ font-size: 1.2rem; font-weight: 600; letter-spacing: -.015em; margin: 2rem 0 .5rem; }}
main p {{ margin: .9rem 0; color: var(--text-2); max-width: 46rem; }}
main strong {{ color: var(--text); font-weight: 600; }}
main ul, main ol {{ color: var(--text-2); max-width: 46rem; padding-left: 1.3rem; }}
main li {{ margin: .5rem 0; }}
main li::marker {{ color: var(--accent); }}
code {{ font-family: var(--mono); font-size: .86em; color: var(--accent-hi);
  background: var(--surface-2); padding: .1rem .4rem; border-radius: 5px; }}
pre {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  padding: 1.1rem 1.3rem; overflow-x: auto; max-width: 46rem; }}
pre code {{ background: none; padding: 0; color: var(--text-2); }}
blockquote {{ border-left: 2px solid var(--accent); margin: 1.4rem 0; padding: .2rem 1.2rem;
  color: var(--muted); }}
table {{ border-collapse: collapse; width: 100%; max-width: 52rem; margin: 1.4rem 0;
  font-size: .95rem; display: block; overflow-x: auto; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .7rem .8rem; text-align: left;
  vertical-align: top; color: var(--text-2); }}
th {{ font-family: var(--mono); font-weight: 500; font-size: .72rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted); }}
td code {{ white-space: nowrap; }}

/* Generated pipeline */
.pipeline {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 1rem; margin: 2rem 0 1rem; }}
.pipeline .stage {{ display: flex; flex-direction: column; align-items: center; gap: .35rem;
  text-align: center; padding: 1rem .6rem; border-radius: 14px; border: 1px solid transparent; }}
.pipeline .stage.paid {{ border-color: {pal.accent_rgba(0.35)}; background: {pal.accent_rgba(0.07)}; }}
.pipeline .stage svg {{ width: 100%; max-width: 11rem; height: auto; }}
.pipeline .stage .n {{ font-family: var(--mono); font-size: .68rem; letter-spacing: .16em;
  color: var(--muted); }}
.pipeline .stage h4 {{ font-size: 1.15rem; font-weight: 600; letter-spacing: -.02em; }}
.pipeline .stage.paid h4 {{ color: var(--accent-hi); }}
.pipeline .stage p {{ font-size: .9rem; line-height: 1.45; color: var(--text-2); margin: 0; }}
.pipeline .stage .mod {{ font-family: var(--mono); font-size: .7rem; color: var(--muted); }}
.pipeline-note {{ display: flex; align-items: center; gap: .9rem; font-family: var(--mono);
  font-size: .8rem; letter-spacing: .04em; color: var(--muted); margin: 1rem 0 0; }}
.pipeline-note i {{ width: 1.6rem; height: 1px; background: var(--accent); flex: 0 0 1.6rem; }}

/* Archive */
.archive-controls {{ display: flex; flex-wrap: wrap; gap: .8rem; margin: 1.4rem 0 1.6rem; }}
.archive-controls input, .archive-controls select {{ font: inherit; font-size: .95rem;
  color: var(--text); background: var(--surface); border: 1px solid var(--line);
  border-radius: 12px; padding: .7rem .9rem; min-height: 48px; }}
.archive-controls input {{ flex: 1 1 16rem; }}
.archive-controls input::placeholder {{ color: var(--muted); }}
ul.archive {{ list-style: none; padding: 0; margin: 0; max-width: none; }}
ul.archive li {{ display: grid; grid-template-columns: 9rem minmax(0, 1fr) auto;
  gap: 1.6rem; align-items: center; padding: 1.3rem 1.1rem;
  border-top: 1px solid var(--line); border-radius: 12px; }}
ul.archive li:last-of-type {{ border-bottom: 1px solid var(--line); }}
ul.archive li:hover {{ background: var(--surface); }}
ul.archive a {{ display: contents; color: var(--text); }}
ul.archive .wk {{ font-family: var(--display); font-size: 1.4rem; font-weight: 600;
  letter-spacing: -.02em; }}
ul.archive .rng {{ display: block; font-family: var(--mono); font-size: .76rem;
  letter-spacing: .04em; color: var(--muted); margin-top: .2rem; }}
ul.archive .lead {{ font-size: 1.02rem; line-height: 1.4; color: var(--text-2); }}
ul.archive .meta {{ font-family: var(--mono); font-size: .78rem; color: var(--muted);
  white-space: nowrap; text-align: right; }}
.archive-empty {{ color: var(--muted); font-style: italic; }}
.next-issue {{ display: grid; grid-template-columns: 9rem minmax(0, 1fr); gap: 1.6rem;
  align-items: center; padding: 1.3rem 1.1rem; margin-top: .4rem;
  border: 1px dashed var(--line-2); border-radius: 12px; color: var(--muted); }}
.next-issue .wk {{ font-family: var(--display); font-size: 1.3rem; font-weight: 600;
  letter-spacing: -.02em; }}
.next-issue b {{ color: var(--accent-hi); font-weight: 600; }}
.next-issue .pulse {{ display: inline-flex; align-items: center; gap: .6rem; }}
.next-issue .pulse i {{ width: .5rem; height: .5rem; border-radius: 50%; background: var(--accent);
  animation: emberPulse 1.6s ease-in-out infinite alternate; }}
@keyframes emberPulse {{ from {{ opacity: .55; }} to {{ opacity: 1; }} }}

/* Sources */
.home-sources {{ margin-top: 3rem; padding-top: 1.6rem; border-top: 1px solid var(--line); }}
.chips {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.2rem 0; }}
.chip {{ display: inline-flex; align-items: center; gap: .5rem; min-height: 34px;
  padding: 0 .85rem; border-radius: 999px; background: var(--surface);
  border: 1px solid var(--line); color: var(--text-2); font-size: .88rem; }}
.chip i {{ width: .5rem; height: .5rem; border-radius: 2px; flex: 0 0 .5rem; }}
ul.feeds {{ list-style: none; padding: 0; margin: 1.4rem 0; max-width: none; }}
ul.feeds li {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: .6rem;
  padding: .85rem .2rem; border-bottom: 1px solid var(--line); }}
ul.feeds li a {{ font-family: var(--display); font-weight: 600; font-size: 1.05rem;
  color: var(--text); }}
ul.feeds li a:hover {{ color: var(--accent); }}
.feed-meta {{ font-family: var(--mono); font-size: .72rem; letter-spacing: .06em;
  color: var(--muted); }}
.feed-names {{ color: var(--text-2); line-height: 1.9; }}

/* Category glyph legend, shared with the digest */
.glyph-row {{ display: flex; flex-wrap: wrap; gap: 1.4rem; margin: 1.4rem 0; }}
.glyph-row span {{ display: inline-flex; align-items: center; gap: .5rem; font-size: .95rem;
  color: var(--text-2); }}
.glyph-row svg {{ width: 1.8rem; height: 1.8rem; }}

.site-footer {{ margin-top: 5rem; padding: 2.2rem 0 3rem; border-top: 1px solid var(--line); }}
.footer-inner {{ display: flex; flex-wrap: wrap; justify-content: space-between;
  align-items: center; gap: 2rem; }}
.site-footer p {{ color: var(--muted); font-size: .9rem; max-width: 34rem; margin: 0; }}
.footer-links {{ display: flex; flex-wrap: wrap; gap: 1.6rem; }}
.footer-links a {{ font-family: var(--mono); font-size: .72rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted); min-height: 44px;
  display: inline-flex; align-items: center; }}
.footer-links a:hover {{ color: var(--text); }}

@media (max-width: 60rem) {{
  .hero {{ grid-template-columns: 1fr; gap: 1rem; }}
  .hero-art {{ order: -1; }}
  .hero-art svg {{ width: min(100%, 26rem); }}
  .latest {{ grid-template-columns: 1fr 1fr; row-gap: 1.1rem; }}
  .latest .cell {{ padding: 0; border-left: 0; }}
  .latest .cell:last-child {{ grid-column: 1 / -1; }}
  ul.archive li, .next-issue {{ grid-template-columns: 1fr; gap: .6rem; }}
  ul.archive .meta {{ text-align: left; }}
}}
@media (max-width: 40rem) {{
  .masthead-inner, main, .footer-inner {{ padding-left: 1.25rem; padding-right: 1.25rem; }}
  .latest {{ grid-template-columns: 1fr; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
  html {{ scroll-behavior: auto; }}
}}
"""


LLMS_TXT = """# Sift
A weekly AI-news digest: many RSS feeds, deduplicated and ranked by one Claude
call, curated for one reader. Static site — scrape freely, but please be polite
(cache; one weekly digest changes per week).

## Machine-readable API (JSON)
Paths are relative to the digests/ directory of this site.
- digests/index.json   Manifest of every weekly digest:
                        { title, tagline, feeds_scanned, latest,
                          digests: [ { week, range, stories, cost_usd, html, json } ] }
- digests/latest.json  The newest digest in full (same schema as a week file).
- digests/<YYYY-WW>.json  One specific ISO-week digest.

## Digest JSON schema
{ "week": "YYYY-WW",
  "stories": [ { "title", "category", "score" (1-10), "rationale",
                 "summary", "needs_verification" (bool),
                 "links": [ { "url", "source" } ] } ],
  "sources_scanned": [ { "name", "count", "ok" (bool) } ] }

## Notes
- week is ISO year-week in UTC. categories: models_research, tooling, infra,
  policy, business. score is importance 1-10 for this reader's interest profile.
- needs_verification=true means the central claim is not from a primary source.
"""
