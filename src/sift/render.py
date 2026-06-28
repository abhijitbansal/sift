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

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sift — {week}</title>
<style>
  :root {{ color-scheme: light dark;
    --fg: #1a1a1a; --bg: #fdfdfb; --muted: #6b6b6b; --line: #e4e2dc; --accent: #b4542e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg: #e8e6e1; --bg: #16181d; --muted: #9a978f; --line: #2c2f36; --accent: #e07a4f; }} }}
  body {{ margin: 2rem auto; max-width: 44rem; padding: 0 1.25rem; background: var(--bg);
    color: var(--fg); font: 16px/1.6 Georgia, 'Times New Roman', serif; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0; }}
  .meta, .rationale, .sources {{ color: var(--muted); font-size: 0.85rem; }}
  h2 {{ font-size: 1.05rem; text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 1px solid var(--line); padding-bottom: 0.3rem; margin-top: 2.5rem; }}
  article {{ margin: 1.5rem 0; }}
  article h3 {{ font-size: 1.15rem; margin: 0 0 0.25rem; }}
  article h3 a {{ color: var(--fg); text-decoration: none; }}
  article h3 a:hover {{ color: var(--accent); }}
  .score {{ color: var(--accent); font-weight: bold; margin-right: 0.4rem; }}
  .flag {{ color: var(--accent); font-size: 0.8rem; border: 1px solid var(--accent);
    border-radius: 3px; padding: 0 0.3rem; margin-left: 0.4rem; }}
  p {{ margin: 0.4rem 0; }}
  .backlink {{ font-size: 0.85rem; }}
  .backlink a {{ color: var(--muted); text-decoration: none; }}
  .backlink a:hover {{ color: var(--accent); }}
</style>
</head>
<body>
<p class="backlink"><a href="index.html">&larr; all digests</a> &middot; <a href="../index.html">about Sift</a></p>
<h1>Sift</h1>
<p class="meta">Week {week} &middot; {count} stories</p>
{sections}
</body>
</html>
"""


def build_digest(week: str, stories: list[dict], clusters: list[list[Item]]) -> dict:
    """Join ranked stories back to their source items; sort by score."""
    enriched = []
    for story in sorted(stories, key=lambda s: s["score"], reverse=True):
        links = [
            {"url": item.url, "source": item.source}
            for cid in story["cluster_ids"]
            for item in clusters[cid]
        ]
        enriched.append({**story, "links": links})
    return {"week": week, "stories": enriched}


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
        sections="\n".join(sections),
    )
    path.write_text(page, encoding="utf-8")


def _article(story: dict) -> str:
    primary_url = story["links"][0]["url"] if story["links"] else "#"
    flag = '<span class="flag">needs verification</span>' if story["needs_verification"] else ""
    sources = ", ".join(
        f'<a href="{escape(link["url"])}">{escape(link["source"])}</a>'
        for link in story["links"]
    )
    return (
        "<article>\n"
        f'<h3><span class="score">{story["score"]}</span>'
        f'<a href="{escape(primary_url)}">{escape(story["title"])}</a>{flag}</h3>\n'
        f"<p>{escape(story['summary'])}</p>\n"
        f'<p class="rationale">{escape(story["rationale"])}</p>\n'
        f'<p class="sources">Covered by: {sources}</p>\n'
        "</article>"
    )
