"""Render the weekly digest as HTML and JSON."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from sift.fetch import Item

CATEGORY_LABELS = {
    "models_research": "Models & Research",
    "tooling": "Tooling",
    "infra": "Infra",
    "policy": "Policy",
    "business": "Business",
}

# Self-contained inline favicon (terracotta tile + cream serif "S"), so each
# digest carries its own icon in email and offline.
_FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'"
    "%3E%3Crect width='32' height='32' rx='7' fill='%23b4542e'/%3E%3Ctext x='16' y='23.5'"
    " font-family='Georgia,serif' font-size='23' font-weight='bold' fill='%23fdfdfb'"
    " text-anchor='middle'%3ES%3C/text%3E%3C/svg%3E"
)

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sift — {week}</title>
<link rel="icon" href="{favicon}" type="image/svg+xml">
<style>
  :root {{ color-scheme: light dark;
    --fg: #1f1b16; --bg: #f7f3ea; --muted: #6f675c; --line: #e0d8c8; --accent: #b4542e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg: #ece7df; --bg: #15130f; --muted: #9a9081; --line: #2e2a23; --accent: #e07a4f; }} }}
  body {{ margin: 2.5rem auto; max-width: 44rem; padding: 0 1.25rem; background: var(--bg);
    color: var(--fg); font: 17px/1.7 Georgia, 'Times New Roman', serif; }}
  header {{ border-bottom: 2px solid var(--fg); padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  h1 {{ font-size: 2.4rem; letter-spacing: -.02em; margin: .2rem 0 0; }}
  .meta {{ color: var(--muted); font-size: .9rem; font-style: italic; margin: .25rem 0 0; }}
  .meta, .rationale, .sources {{ color: var(--muted); }}
  .rationale, .sources {{ font-size: .85rem; }}
  h2 {{ font-size: .95rem; text-transform: uppercase; letter-spacing: .12em;
    border-bottom: 1px solid var(--line); padding-bottom: .3rem; margin-top: 2.6rem;
    color: var(--accent); }}
  article {{ display: flex; gap: 1rem; margin: 1.7rem 0; }}
  .score {{ flex: 0 0 auto; width: 2.5rem; height: 2.5rem; border-radius: 50%;
    background: var(--accent); color: var(--bg); font-weight: bold; font-size: 1.05rem;
    display: flex; align-items: center; justify-content: center; }}
  .art-body {{ flex: 1; min-width: 0; }}
  article h3 {{ font-size: 1.2rem; line-height: 1.25; margin: .1rem 0 .35rem; }}
  article h3 a {{ color: var(--fg); text-decoration: none; }}
  article h3 a:hover {{ color: var(--accent); }}
  .summary {{ margin: .25rem 0; }}
  .rationale {{ margin: .3rem 0 0; font-style: italic; }}
  .sources {{ margin: .35rem 0 0; }}
  .sources a {{ color: var(--muted); }}
  .flag {{ color: var(--accent); font-size: .68rem; text-transform: uppercase;
    letter-spacing: .06em; border: 1px solid var(--accent); border-radius: 3px;
    padding: .05rem .35rem; margin-left: .45rem; white-space: nowrap; }}
  .backlink {{ font-size: .82rem; margin: 0 0 .4rem; }}
  .backlink a {{ color: var(--muted); text-decoration: none; }}
  .backlink a:hover {{ color: var(--accent); }}
  .scanned {{ margin-top: 2.8rem; }}
  .scanned-list {{ list-style: none; padding: 0; margin: .4rem 0 0; display: flex;
    flex-wrap: wrap; gap: .35rem .9rem; font-size: .82rem; color: var(--muted); }}
  .scanned-list li {{ white-space: nowrap; }}
  .cnt {{ color: var(--fg); font-weight: bold; }}
  .cnt.dead {{ color: var(--accent); font-weight: normal; font-style: italic; }}
  footer {{ margin-top: 3rem; padding-top: 1.1rem; border-top: 1px solid var(--line);
    color: var(--muted); font-size: .82rem; font-style: italic; }}
</style>
</head>
<body>
<header>
<p class="backlink"><a href="index.html">&larr; all issues</a> &middot; <a href="../index.html">about Sift</a></p>
<h1>Sift</h1>
<p class="meta">Week {week} &middot; {count} stories</p>
</header>
{sections}
{scanned}
<footer>Curated weekly from your feeds — one Claude call, everything else local and free.</footer>
</body>
</html>
"""


def build_digest(
    week: str,
    stories: list[dict],
    clusters: list[list[Item]],
    feed_results: list | None = None,
) -> dict:
    """Join ranked stories back to their source items; sort by score.

    feed_results (fetch.FeedResult) records which sources were scanned this run
    and how many items each returned, for transparency in the digest.
    """
    enriched = []
    for story in sorted(stories, key=lambda s: s["score"], reverse=True):
        links = [
            {"url": item.url, "source": item.source}
            for cid in story["cluster_ids"]
            for item in clusters[cid]
        ]
        enriched.append({**story, "links": links})
    digest = {"week": week, "stories": enriched}
    if feed_results is not None:
        digest["sources_scanned"] = [
            {"name": r.name, "count": r.count, "ok": r.ok} for r in feed_results
        ]
    return digest


def render_json(digest: dict, path: Path) -> None:
    path.write_text(json.dumps(digest, indent=2) + "\n", encoding="utf-8")


def render_html(digest: dict, path: Path) -> None:
    sections = []
    for category, label in CATEGORY_LABELS.items():
        stories = [s for s in digest["stories"] if s["category"] == category]
        if not stories:
            continue
        articles = "\n".join(_article(s) for s in stories)
        sections.append(f"<h2>{escape(label)}</h2>\n{articles}")
    page = _PAGE.format(
        week=escape(digest["week"]),
        count=len(digest["stories"]),
        favicon=_FAVICON,
        sections="\n".join(sections),
        scanned=_sources_scanned_html(digest),
    )
    path.write_text(page, encoding="utf-8")


def _sources_scanned_html(digest: dict) -> str:
    sources = digest.get("sources_scanned")
    if not sources:
        return ""
    items = "".join(
        f"<li>{escape(s['name'])} "
        + (
            f'<span class="cnt">{s["count"]}</span>'
            if s["ok"]
            else '<span class="cnt dead">dead</span>'
        )
        + "</li>"
        for s in sources
    )
    live = sum(1 for s in sources if s["ok"])
    return (
        '<section class="scanned">\n'
        f"<h2>Sources scanned &middot; {live}/{len(sources)} live</h2>\n"
        f'<ul class="scanned-list">{items}</ul>\n'
        "</section>"
    )


def _article(story: dict) -> str:
    primary_url = story["links"][0]["url"] if story["links"] else "#"
    flag = '<span class="flag">needs verification</span>' if story["needs_verification"] else ""
    sources = ", ".join(
        f'<a href="{escape(link["url"])}">{escape(link["source"])}</a>'
        for link in story["links"]
    )
    return (
        "<article>\n"
        f'<span class="score" title="importance {story["score"]}/10">{story["score"]}</span>\n'
        '<div class="art-body">\n'
        f'<h3><a href="{escape(primary_url)}">{escape(story["title"])}</a>{flag}</h3>\n'
        f'<p class="summary">{escape(story["summary"])}</p>\n'
        f'<p class="rationale">{escape(story["rationale"])}</p>\n'
        f'<p class="sources">Covered by {sources}</p>\n'
        "</div>\n"
        "</article>"
    )
