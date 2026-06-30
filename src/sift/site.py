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

from sift import card, store
from sift.config import Config
from sift.meta import abs_url, og_tags
from sift.urls import safe_href
from sift.weeks import week_end, week_range

log = logging.getLogger("sift.site")

TAGLINE = "A weekly dispatch of AI signal — curated for one reader"

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


def build_site(root: Path, db_path: Path, cfg: Config) -> int:
    """Render every site page. Returns the number of pages written."""
    docs = root / "docs"
    assets = docs / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "sift.css").write_text(SITE_CSS, encoding="utf-8")
    (assets / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    (docs / "site.webmanifest").write_text(WEBMANIFEST, encoding="utf-8")
    card.render_static_card(assets / "og.png")  # best-effort; static og:image + fallback

    out_dir = docs / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    history = _history_by_week(db_path)
    entries = _archive_entries(out_dir, history)
    _refresh_digests(out_dir, history, cfg)  # re-render archived digests + cover cards

    content_dir = root / "content"
    today = date.today()
    pages = 0
    for slug, (_, title, filename) in PROSE_PAGES.items():
        body = _render_prose(content_dir / filename)
        if slug == "index":
            if entries:
                body = _latest_issue_hero(entries[0], today) + body
            body = body + _home_sources_html(cfg)
        elif slug == "sources":
            body = _configured_feeds_html(cfg) + body
        rel = "" if slug == "index" else f"{slug}.html"
        (docs / f"{slug}.html").write_text(
            _wrap(title, body, prefix="", active=slug, cfg=cfg, rel=rel), encoding="utf-8"
        )
        pages += 1

    (out_dir / "index.html").write_text(
        _wrap(
            "Sift — digest archive", _archive_body(entries),
            prefix="../", active="digests", cfg=cfg, rel="digests/index.html",
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
            render.render_html(
                digest, out_dir / f"{week}.html", site_url=cfg.site_url, cost_usd=cost
            )
            if stories:
                counts: dict[str, int] = {}
                for s in stories:
                    counts[s["category"]] = counts.get(s["category"], 0) + 1
                card.render_issue_card(
                    out_dir / f"{week}.png",
                    week=week,
                    range_label=week_range(week),
                    headline=stories[0].get("title", "Weekly AI signal"),
                    category_counts=counts,
                    story_count=len(stories),
                    feed_count=len(digest.get("sources_scanned", []) or cfg.feeds),
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
    if not path.exists():
        return f"<p><em>Content file missing: {escape(path.name)}</em></p>"
    return md.markdown(path.read_text(encoding="utf-8"), extensions=["extra", "sane_lists"])


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
        entries.append(
            ArchiveEntry(
                week=week,
                range_label=week_range(week),
                count=len(data.get("stories", [])),
                cost_usd=record.cost_usd if record else 0.0,
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


def _latest_issue_hero(entry: ArchiveEntry, today: date) -> str:
    # The next-issue label is fully derivable from the entry's week + today, so we
    # compute it here rather than threading a separate (forgettable) argument.
    next_label = _next_issue_label(entry.week, today)
    next_html = (
        f'<span class="latest-next">Next issue &middot; {escape(next_label)}</span>'
        if next_label
        else ""
    )
    return (
        '<aside class="latest">'
        '<span class="kicker">Latest issue</span>'
        f'<a class="latest-link" href="digests/{escape(entry.week)}.html">'
        f"<span class=\"latest-wk\">Week {escape(entry.week)}</span>"
        f'<span class="latest-rng">{escape(entry.range_label)}</span></a>'
        f'<span class="latest-meta">{_meta_line(entry)}</span>'
        f"{next_html}"
        "</aside>\n"
    )


def _archive_body(entries: list[ArchiveEntry]) -> str:
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
        f'<span class="wk">Week {escape(e.week)}</span>'
        f'<span class="rng">{escape(e.range_label)}</span></a>'
        f'<span class="meta">{_meta_line(e)}</span></li>'
        for e in entries
    )
    return (
        "<h1>Digest archive</h1>\n"
        '<div class="archive-controls">\n'
        '<input id="archive-filter" type="search" placeholder="Filter issues…" '
        'aria-label="Filter issues">\n'
        '<select id="archive-jump" aria-label="Jump to an issue">\n'
        '<option value="">Jump to an issue…</option>\n'
        f"{options}\n</select>\n</div>\n"
        f'<ul class="archive" id="archive-list">\n{rows}\n</ul>\n'
        f"<p class=\"archive-empty\" id=\"archive-empty\" hidden>No issues match that filter.</p>\n"
        f"{_ARCHIVE_JS}"
    )


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
    title: str, body_html: str, *, prefix: str, active: str, cfg: Config, rel: str
) -> str:
    nav_links = "".join(
        f'<a href="{prefix}{href}"'
        + (' class="active"' if slug == active else "")
        + f">{escape(label)}</a>"
        for href, label, slug in NAV
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
        brand=f"{prefix}index.html",
        tagline=escape(TAGLINE),
        nav=nav_links,
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
<meta name="theme-color" content="#b4542e">
{og}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
<a class="brand" href="{brand}">Sift</a>
<p class="tagline">{tagline}</p>
<nav>{nav}</nav>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
<p>Sift &mdash; a weekly AI-news curation pipeline for one reader. One Claude call
per week; everything else local and free.</p>
</footer>
</body>
</html>
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


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Sift">
  <rect width="32" height="32" rx="7" fill="#b4542e"/>
  <text x="16" y="23.5" font-family="Georgia, 'Times New Roman', serif" font-size="23" font-weight="bold" fill="#fdfdfb" text-anchor="middle">S</text>
</svg>
"""

# Raster icons (favicon.ico, favicon-16/32.png, apple-touch-icon.png) are
# committed assets generated by scripts/gen_favicons.py from the same mark.
WEBMANIFEST = """{
  "name": "Sift",
  "short_name": "Sift",
  "description": "A weekly AI-news digest, curated for one reader.",
  "theme_color": "#b4542e",
  "background_color": "#15130f",
  "display": "minimal-ui",
  "icons": [
    { "src": "assets/favicon.svg", "type": "image/svg+xml", "sizes": "any" },
    { "src": "assets/favicon-32.png", "type": "image/png", "sizes": "32x32" },
    { "src": "assets/favicon-16.png", "type": "image/png", "sizes": "16x16" },
    { "src": "assets/apple-touch-icon.png", "type": "image/png", "sizes": "180x180" }
  ]
}
"""


SITE_CSS = """:root {
  color-scheme: light dark;
  --fg: #241f18; --bg: #f7f3ea; --muted: #6c6353; --line: #e5dcc8; --line-2: #d3c8b0;
  --accent: #b4542e; --accent-soft: #d98a5f; --card: #fffdf7; --card-2: #f1ead9;
  --shadow: rgba(60,45,30,.10);
  --cat-models: #5b54d6; --cat-tooling: #0d9488; --cat-infra: #b45309;
  --cat-policy: #be123c; --cat-business: #15803d;
  --display: "Fraunces", Georgia, "Times New Roman", serif;
  --body: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --fg: #efe7d9; --bg: #1b1410; --muted: #ad9f85; --line: #3b2d20; --line-2: #4c3a29;
    --accent: #e07a4f; --accent-soft: #b4542e; --card: #241b14; --card-2: #2d2218;
    --shadow: rgba(0,0,0,.5);
    --cat-models: #8b84f0; --cat-tooling: #2dd4bf; --cat-infra: #f59e0b;
    --cat-policy: #fb7185; --cat-business: #4ade80; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15.5px/1.6 var(--body); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
::selection { background: var(--accent); color: var(--bg); }
.skip { position: absolute; left: -9999px; top: 0; z-index: 80; background: var(--accent);
  color: #fff7f1; font-family: var(--mono); font-size: .75rem; font-weight: 700;
  padding: .65rem 1rem; border-radius: 0 0 9px 0; }
.skip:focus { left: 0; }

/* Masthead */
.masthead { max-width: 48rem; margin: 0 auto; padding: 1.9rem 1.25rem 1rem;
  border-bottom: 2px solid var(--fg); }
.brand { display: block; font-family: var(--display); font-weight: 900;
  font-size: clamp(2.4rem, 8vw, 3.6rem); line-height: .95; letter-spacing: -.02em;
  color: var(--fg); text-decoration: none; font-optical-sizing: auto; }
.tagline { margin: .35rem 0 1rem; color: var(--muted); font-size: .95rem; }
.masthead nav { display: flex; flex-wrap: wrap; gap: 1.1rem; padding-top: .6rem;
  border-top: 1px solid var(--line); }
.masthead nav a { color: var(--muted); text-decoration: none; font-family: var(--mono);
  font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; padding-bottom: 3px;
  border-bottom: 2px solid transparent; transition: color .15s, border-color .15s; min-height: 40px;
  display: inline-flex; align-items: center; }
.masthead nav a:hover, .masthead nav a:focus-visible { color: var(--fg); }
.masthead nav a.active { color: var(--accent); border-color: var(--accent); }

main { max-width: 48rem; margin: 2.2rem auto; padding: 0 1.25rem; }
h1 { font-family: var(--display); font-weight: 600; font-size: clamp(1.8rem, 5vw, 2.4rem);
  line-height: 1.1; letter-spacing: -.015em; margin: 0 0 1rem; }
h2 { font-family: var(--display); font-weight: 600; font-size: 1.35rem; letter-spacing: -.01em;
  border-bottom: 1px solid var(--line); padding-bottom: .35rem; margin: 2.5rem 0 .8rem; }
h3 { font-family: var(--display); font-weight: 600; font-size: 1.12rem; margin: 1.8rem 0 .4rem; }
p { margin: .7rem 0; }
code { background: var(--card-2); padding: .1rem .38rem; border-radius: 4px;
  font: .85em var(--mono); }
pre { background: var(--card-2); padding: 1rem 1.1rem; border-radius: 8px; overflow-x: auto;
  border: 1px solid var(--line); box-shadow: 0 1px 2px var(--shadow); }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.3rem 0; font-size: .92rem; }
th, td { border: 1px solid var(--line); padding: .5rem .65rem; text-align: left; vertical-align: top; }
th { background: var(--card-2); font-family: var(--mono); font-weight: 600; font-size: .82rem;
  text-transform: uppercase; letter-spacing: .04em; }
blockquote { border-left: 3px solid var(--accent); margin: 1.3rem 0; padding: .3rem 1.1rem;
  color: var(--muted); font-style: italic; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 3px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }

/* Latest-issue hero (home) — dashboard card */
.latest { display: flex; flex-direction: column; gap: .15rem; background: var(--card);
  border: 1px solid var(--line); border-top: 3px solid var(--accent); border-radius: 12px;
  padding: 1.1rem 1.3rem; margin: 0 0 2.2rem; box-shadow: 0 2px 14px var(--shadow); }
.latest .kicker { font-family: var(--mono); font-size: .68rem; text-transform: uppercase;
  letter-spacing: .14em; color: var(--accent); font-weight: 700; }
.latest-link { text-decoration: none; color: var(--fg); display: flex; flex-wrap: wrap;
  align-items: baseline; gap: .6rem; margin-top: .3rem; }
.latest-wk { font-family: var(--display); font-weight: 600; font-size: 1.4rem; }
.latest-rng { color: var(--muted); }
.latest-link:hover .latest-wk { color: var(--accent); }
.latest-meta { font-family: var(--mono); color: var(--muted); font-size: .8rem; margin-top: .25rem; }
.latest-next { font-family: var(--mono); color: var(--accent); font-size: .72rem; text-transform: uppercase;
  letter-spacing: .08em; margin-top: .4rem; }

/* Archive */
.archive-controls { display: flex; flex-wrap: wrap; gap: .7rem; margin: 1.2rem 0 1.5rem; }
.archive-controls input, .archive-controls select { font: inherit; font-size: .92rem;
  color: var(--fg); background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; padding: .5rem .7rem; min-height: 40px; }
.archive-controls input { flex: 1 1 12rem; }
ul.archive { list-style: none; padding: 0; margin: 0; }
ul.archive li { display: flex; justify-content: space-between; align-items: baseline;
  gap: 1rem; padding: .85rem .2rem; border-bottom: 1px solid var(--line); }
ul.archive li a { text-decoration: none; color: var(--fg); display: flex; gap: .7rem;
  align-items: baseline; flex-wrap: wrap; }
ul.archive .wk { font-family: var(--display); font-weight: 600; font-size: 1.1rem; }
ul.archive li a:hover .wk { color: var(--accent); }
ul.archive .rng { color: var(--muted); font-size: .9rem; }
ul.archive .meta { font-family: var(--mono); color: var(--muted); font-size: .76rem; white-space: nowrap; }
.archive-empty { color: var(--muted); font-style: italic; }

/* Source lists */
.home-sources { margin-top: 2.8rem; padding-top: 1.4rem; border-top: 1px solid var(--line); }
.feed-names { color: var(--muted); line-height: 1.9; }
ul.feeds { list-style: none; padding: 0; margin: 1.2rem 0; }
ul.feeds li { padding: .55rem .2rem; border-bottom: 1px solid var(--line); }
ul.feeds li a { font-family: var(--display); font-weight: 600; text-decoration: none; }
ul.feeds li a:hover { text-decoration: underline; }
.feed-meta { font-family: var(--mono); color: var(--muted); font-size: .74rem; margin-left: .4rem; }

/* Pipeline flow diagram */
.flow { margin: 1.6rem 0; }
.flow .stage { border: 1px solid var(--line); border-radius: 10px; padding: .8rem 1.1rem;
  background: var(--card); box-shadow: 0 1px 3px var(--shadow); }
.flow .stage.paid { border-color: var(--accent); border-width: 2px;
  box-shadow: 0 2px 12px var(--shadow); }
.flow .stage h4 { font-family: var(--display); font-weight: 600; margin: 0 0 .25rem; font-size: 1.05rem; }
.flow .stage.paid h4 { color: var(--accent); }
.flow .stage p { margin: .15rem 0 .45rem; font-size: .9rem; }
.flow .stage .mod { color: var(--muted); font-size: .74rem; font-family: var(--mono); }
.flow .arrow { text-align: center; color: var(--accent); font-size: 1.35rem; line-height: 1; margin: .3rem 0; }

.site-footer { max-width: 48rem; margin: 3.5rem auto 2.5rem; padding: 1.3rem 1.25rem 0;
  border-top: 1px solid var(--line); color: var(--muted); font-size: .82rem; }
"""
