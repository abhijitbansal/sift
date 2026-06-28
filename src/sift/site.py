"""Generate the static GitHub Pages site under docs/.

Pages: an explainer (index), a usage guide, a roadmap (all from content/*.md),
and a digest archive index. All share docs/assets/sift.css for one visual
language; the weekly digests themselves stay self-contained so they also work
in email and offline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path

import markdown as md

from sift import store
from sift.config import Config

log = logging.getLogger("sift.site")

# slug -> (nav label, page title, content filename)
PROSE_PAGES = {
    "index": ("Home", "Sift — weekly AI-news curation", "index.md"),
    "guide": ("Guide", "Sift — usage guide", "guide.md"),
    "roadmap": ("Roadmap", "Sift — roadmap", "roadmap.md"),
}

NAV = [
    ("index.html", "Home", "index"),
    ("guide.html", "Guide", "guide"),
    ("roadmap.html", "Roadmap", "roadmap"),
    ("digests/index.html", "Digests", "digests"),
]


@dataclass(frozen=True)
class ArchiveEntry:
    week: str
    count: int
    cost_usd: float


def build_site(root: Path, db_path: Path, cfg: Config) -> int:
    """Render every site page. Returns the number of pages written."""
    docs = root / "docs"
    assets = docs / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "sift.css").write_text(SITE_CSS, encoding="utf-8")

    content_dir = root / "content"
    pages = 0
    for slug, (_, title, filename) in PROSE_PAGES.items():
        body = _render_prose(content_dir / filename)
        (docs / f"{slug}.html").write_text(
            _wrap(title, body, prefix="", active=slug), encoding="utf-8"
        )
        pages += 1

    out_dir = docs / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = _archive_entries(out_dir, _history_by_week(db_path))
    (out_dir / "index.html").write_text(
        _wrap("Sift — digest archive", _archive_body(entries), prefix="../", active="digests"),
        encoding="utf-8",
    )
    pages += 1
    log.info("Built %d site pages (%d archived digests)", pages, len(entries))
    return pages


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
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # ValueError covers JSON + UnicodeDecodeError
            log.warning("Skipping unreadable digest json: %s", json_path)
            continue
        record = history.get(week)
        entries.append(
            ArchiveEntry(
                week=week,
                count=len(data.get("stories", [])),
                cost_usd=record.cost_usd if record else 0.0,
            )
        )
    return entries


def _archive_body(entries: list[ArchiveEntry]) -> str:
    if not entries:
        return (
            "<p>No digests yet. Run <code>uv run sift run</code> to generate the first one.</p>"
        )
    rows = "\n".join(
        f'<li><a href="{escape(e.week)}.html">Week {escape(e.week)}</a>'
        f'<span class="meta">{e.count} stories'
        + (f" &middot; ${e.cost_usd:.4f}" if e.cost_usd else "")
        + "</span></li>"
        for e in entries
    )
    return f'<h1>Digest archive</h1>\n<ul class="archive">\n{rows}\n</ul>'


def _wrap(title: str, body_html: str, *, prefix: str, active: str) -> str:
    nav_links = "".join(
        f'<a href="{prefix}{href}"'
        + (' class="active"' if slug == active else "")
        + f">{escape(label)}</a>"
        for href, label, slug in NAV
    )
    return _PAGE_TEMPLATE.format(
        title=escape(title),
        css=f"{prefix}assets/sift.css",
        brand=f"{prefix}index.html",
        nav=nav_links,
        body=body_html,
    )


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<header class="site-header">
<a class="brand" href="{brand}">Sift</a>
<nav>{nav}</nav>
</header>
<main>
{body}
</main>
<footer class="site-footer">
<p>Sift — a weekly AI-news curation pipeline for one reader. One Claude call per
week; everything else local and free.</p>
</footer>
</body>
</html>
"""


SITE_CSS = """:root {
  color-scheme: light dark;
  --fg: #1a1a1a; --bg: #fdfdfb; --muted: #6b6b6b; --line: #e4e2dc; --accent: #b4542e;
  --card: #f6f4ef;
}
@media (prefers-color-scheme: dark) {
  :root { --fg: #e8e6e1; --bg: #16181d; --muted: #9a978f; --line: #2c2f36;
    --accent: #e07a4f; --card: #1d2027; }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.65 Georgia, 'Times New Roman', serif;
}
main { max-width: 44rem; margin: 2.5rem auto; padding: 0 1.25rem; }
.site-header {
  display: flex; align-items: baseline; gap: 1.5rem; flex-wrap: wrap;
  max-width: 44rem; margin: 0 auto; padding: 1.25rem; border-bottom: 1px solid var(--line);
}
.brand { font-size: 1.4rem; font-weight: bold; color: var(--fg); text-decoration: none; }
.site-header nav { display: flex; gap: 1.1rem; flex-wrap: wrap; }
.site-header nav a {
  color: var(--muted); text-decoration: none; font-size: 0.95rem;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.site-header nav a:hover, .site-header nav a.active { color: var(--accent); }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 0 0 1rem; }
h2 { font-size: 1.25rem; text-transform: uppercase; letter-spacing: 0.07em;
  border-bottom: 1px solid var(--line); padding-bottom: 0.3rem; margin-top: 2.5rem; }
h3 { font-size: 1.1rem; margin-top: 1.8rem; }
a { color: var(--accent); }
code { background: var(--card); padding: 0.1rem 0.35rem; border-radius: 3px;
  font: 0.85em ui-monospace, SFMono-Regular, Menlo, monospace; }
pre { background: var(--card); padding: 1rem; border-radius: 6px; overflow-x: auto;
  border: 1px solid var(--line); }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; font-size: 0.95rem; }
th, td { border: 1px solid var(--line); padding: 0.45rem 0.6rem; text-align: left; }
th { background: var(--card); }
blockquote { border-left: 3px solid var(--accent); margin: 1.2rem 0; padding: 0.2rem 1rem;
  color: var(--muted); }
ul.archive { list-style: none; padding: 0; }
ul.archive li { display: flex; justify-content: space-between; align-items: baseline;
  gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid var(--line); }
ul.archive .meta { color: var(--muted); font-size: 0.85rem; white-space: nowrap; }
.site-footer { max-width: 44rem; margin: 3rem auto 2rem; padding: 1.2rem 1.25rem 0;
  border-top: 1px solid var(--line); color: var(--muted); font-size: 0.85rem; }
"""
