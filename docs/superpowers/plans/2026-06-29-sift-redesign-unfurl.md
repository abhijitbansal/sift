# Sift Redesign + Teams Unfurl + Ford Boost — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Sift site/digest to a tech-brief dashboard, fix Teams/Slack link unfurl with a static-raster OG card, and up-weight watched entities (Ford) in ranking.

**Architecture:** New leaf modules (`weeks.py`, `meta.py`, `card.py`, `urls.display_domain`, config fields) are built test-first, then consumed by the two renderers (`render.py` digest, `site.py` site). The approved mockup `.scratch/redesign-mockup.html` is the visual source of truth: its CSS/markup is ported into `site.py` (web-font variant) and `render.py` (system-font variant).

**Tech Stack:** Python 3.11+, stdlib (`datetime`, `html`, `urllib.parse`), Pillow (raster OG card), pytest + pytest-cov.

## Global Constraints

- Immutable data — never mutate inputs; return new objects (frozen dataclasses, new dicts).
- Digest (`render.py`) stays **self-contained**: single file, inline CSS, **no web fonts / no external CSS/JS** (system stacks only). The **site** (`site.py`) may load Google Fonts.
- All href/URL sinks go through `urls.safe_href`; all text through `html.escape`.
- `og:image` MUST be a static PNG (never SVG/GIF) with declared `og:image:width`/`height` and `twitter:card=summary_large_image`. `og:url`/`og:image` absolute https on this site (`site_url`).
- `site_url` default: `https://abhijitbansal.github.io/sift/` (trailing slash). OG dims: 1200×630.
- Card generation is **best-effort**: failure logs + falls back to static `docs/assets/og.png`; never breaks `sift run`.
- Keep coverage ≥80% (currently 93%). One logical change per commit.
- Color tokens / category palette / copy: exactly as in `docs/superpowers/specs/2026-06-29-sift-redesign-design.md`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/sift/weeks.py` *(new)* | `week_end`, `week_range` — ISO-week→date, shared by site+render |
| `src/sift/meta.py` *(new)* | `og_tags(...)` → the OG/Twitter `<head>` block; `abs_url(base, rel)` |
| `src/sift/card.py` *(new)* | Pillow OG cards: `render_issue_card`, `render_static_card` (best-effort) |
| `src/sift/urls.py` | add `display_domain(url)` |
| `src/sift/config.py` | add `boost: tuple[str,...]`, `site_url: str` |
| `src/sift/rank.py` | boost hint in `build_prompt` |
| `src/sift/render.py` | dashboard digest + OG head + source chips + glance; thread range/cost/site_url |
| `src/sift/site.py` | theme overhaul + OG head + static og.png + per-issue cards + weeks + skip link |
| `src/sift/cli.py` | thread `cost_usd`/`site_url` into digest build; card gen via build_site |
| `pyproject.toml` | Pillow dev→runtime |
| `config.toml` / `config.example.toml` | `boost`, `site_url` |
| `content/guide.md`, `content/sources.md` | light copy for boost |

---

## Task 1: `weeks.py` shared week helpers

**Files:** Create `src/sift/weeks.py`; Test `tests/test_weeks.py`; Modify `src/sift/site.py` (use it).
**Interfaces — Produces:** `week_end(week: str) -> date | None`, `week_range(week: str) -> str`.

- [ ] **Step 1: failing test** — `tests/test_weeks.py`:
```python
from datetime import date
from sift.weeks import week_end, week_range

def test_week_end_is_iso_sunday():
    assert week_end("2026-26") == date(2026, 6, 28)

def test_week_end_none_when_unparseable():
    assert week_end("nope") is None
    assert week_end("2026-99") is None

def test_week_range_same_month():
    assert week_range("2026-26") == "Jun 22–28, 2026"

def test_week_range_cross_month_and_empty():
    assert "–" in week_range("2026-05")
    assert week_range("bad") == ""
```
- [ ] **Step 2:** `uv run pytest tests/test_weeks.py -q` → FAIL (no module).
- [ ] **Step 3:** create `src/sift/weeks.py`:
```python
"""Shared ISO-week → date helpers (week id 'YYYY-WW'). Single source of truth."""
from __future__ import annotations
from datetime import date, timedelta

def week_end(week: str) -> date | None:
    """The Sunday that ISO week id 'YYYY-WW' ends on, or None if unparseable."""
    try:
        year_s, week_s = week.split("-")
        return date.fromisocalendar(int(year_s), int(week_s), 7)
    except (ValueError, TypeError):
        return None

def week_range(week: str) -> str:
    """Human label for 'YYYY-WW', e.g. 'Jun 22–28, 2026'. '' if unparseable."""
    end = week_end(week)
    if end is None:
        return ""
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}, {end.year}"
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"
```
- [ ] **Step 4:** `uv run pytest tests/test_weeks.py -q` → PASS.
- [ ] **Step 5:** In `site.py`, replace `_week_end` body with `from sift.weeks import week_end, week_range` and make `_week_end`/`_week_range` delegate (or replace call sites). Keep `_next_issue_label` using `week_end`. Run `uv run pytest tests/test_site.py -q` → PASS.
- [ ] **Step 6: commit** `refactor: extract shared week helpers into weeks.py`.

---

## Task 2: `urls.display_domain`

**Files:** Modify `src/sift/urls.py`; Test `tests/test_urls.py`.
**Interfaces — Produces:** `display_domain(url: str) -> str`.

- [ ] **Step 1: failing test** — add to `tests/test_urls.py`:
```python
from sift.urls import display_domain

def test_display_domain_strips_www_and_port():
    assert display_domain("https://www.latent.space/p/x") == "latent.space"
    assert display_domain("https://semgrep.dev:443/blog") == "semgrep.dev"

def test_display_domain_non_http_is_empty():
    assert display_domain("javascript:alert(1)") == ""
    assert display_domain("not a url") == ""
```
- [ ] **Step 2:** `uv run pytest tests/test_urls.py -q` → FAIL.
- [ ] **Step 3:** add to `urls.py`:
```python
def display_domain(url: str) -> str:
    """Bare display host for a source chip: lowercased netloc minus 'www.' and
    port. '' for non-http(s) urls (so it never renders an unsafe label)."""
    if not is_http_url(url):
        return ""
    host = (urlsplit(_clean(url)).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host
```
- [ ] **Step 4:** `uv run pytest tests/test_urls.py -q` → PASS.
- [ ] **Step 5: commit** `feat(urls): add display_domain for source chips`.

---

## Task 3: config `boost` + `site_url`

**Files:** Modify `src/sift/config.py`; Test `tests/test_config.py`.
**Interfaces — Produces:** `Config.boost: tuple[str,...]` (default `()`), `Config.site_url: str` (default `DEFAULT_SITE_URL`).

- [ ] **Step 1: failing test** — `tests/test_config.py` (write a config with `boost = ["Ford", " "]` and `site_url`):
```python
def test_boost_and_site_url(tmp_path):
    cfg = _write(tmp_path, 'boost = ["Ford", "  "]\nsite_url = "https://x.test/sift/"\n')
    assert cfg.boost == ("Ford",)
    assert cfg.site_url == "https://x.test/sift/"

def test_boost_defaults_empty_and_site_url_default(tmp_path):
    cfg = _write(tmp_path, "")
    assert cfg.boost == ()
    assert cfg.site_url.endswith("/sift/")
```
(Use the file's existing helper to build a minimal valid config; add the snippet inside `[sift]`.)
- [ ] **Step 2:** `uv run pytest tests/test_config.py -q` → FAIL.
- [ ] **Step 3:** in `config.py`: add `DEFAULT_SITE_URL = "https://abhijitbansal.github.io/sift/"`; add `boost: tuple[str, ...] = ()` and `site_url: str = DEFAULT_SITE_URL` to `Config`; in `load_config`:
```python
    boost = tuple(str(b).strip() for b in sift_cfg.get("boost", []) if str(b).strip())
    site_url = str(sift_cfg.get("site_url", DEFAULT_SITE_URL))
```
and pass `boost=boost, site_url=site_url` into the `Config(...)` constructor.
- [ ] **Step 4:** `uv run pytest tests/test_config.py -q` → PASS.
- [ ] **Step 5: commit** `feat(config): add boost watchlist and site_url`.

---

## Task 4: rank boost hint

**Files:** Modify `src/sift/rank.py:build_prompt`; Test `tests/test_rank.py`.
**Interfaces — Consumes:** `config.boost`.

- [ ] **Step 1: failing test** — add to `tests/test_rank.py` (build a Config with `boost=("Ford",)`):
```python
def test_build_prompt_includes_boost_line():
    cfg = _cfg(boost=("Ford",))
    p = rank.build_prompt([], cfg)
    assert "Ford" in p and "raise their" in p.lower()

def test_build_prompt_omits_boost_when_empty():
    p = rank.build_prompt([], _cfg(boost=()))
    assert "raise their" not in p.lower()
```
- [ ] **Step 2:** `uv run pytest tests/test_rank.py -q` → FAIL.
- [ ] **Step 3:** in `build_prompt`, after the source-weighting block:
```python
    if config.boost:
        boosted = ", ".join(config.boost)
        parts.append(
            "Strongly prioritize stories about these entities/topics — raise their "
            f"importance score by ~2 points and surface them even when borderline: {boosted}.\n"
        )
```
- [ ] **Step 4:** `uv run pytest tests/test_rank.py -q` → PASS.
- [ ] **Step 5: commit** `feat(rank): up-weight boosted entities in the ranking prompt`.

---

## Task 5: `meta.py` OG head block

**Files:** Create `src/sift/meta.py`; Test `tests/test_meta.py`.
**Interfaces — Produces:** `og_tags(*, title, description, url, image, image_alt, width=1200, height=630, site_name="Sift") -> str`; `abs_url(base: str, rel: str) -> str`.

- [ ] **Step 1: failing test** — `tests/test_meta.py`:
```python
from sift.meta import og_tags, abs_url

def test_abs_url_joins_trailing_slash_base():
    assert abs_url("https://x.test/sift/", "digests/2026-26.html") == "https://x.test/sift/digests/2026-26.html"
    assert abs_url("https://x.test/sift/", "") == "https://x.test/sift/"

def test_og_tags_has_static_image_card_signals():
    t = og_tags(title="T", description="D", url="https://x.test/sift/",
                image="https://x.test/sift/og.png", image_alt="A")
    assert 'property="og:image" content="https://x.test/sift/og.png"' in t
    assert 'property="og:image:width" content="1200"' in t
    assert 'property="og:image:height" content="630"' in t
    assert 'name="twitter:card" content="summary_large_image"' in t

def test_og_tags_escapes_quotes():
    assert '&quot;' in og_tags(title='a"b', description="d", url="u", image="i", image_alt="x")
```
- [ ] **Step 2:** `uv run pytest tests/test_meta.py -q` → FAIL.
- [ ] **Step 3:** create `src/sift/meta.py`:
```python
"""Open Graph / Twitter head block — the static-raster large-image card that
makes Teams/Slack render a titled link preview. og:image must be a PNG/JPG with
declared width/height + twitter:card=summary_large_image (verified against the
known-good claude-skills page)."""
from __future__ import annotations
from html import escape
from urllib.parse import urljoin

def abs_url(base: str, rel: str) -> str:
    """Absolute URL for a site-relative path against a trailing-slash base."""
    return urljoin(base, rel)

def og_tags(*, title: str, description: str, url: str, image: str, image_alt: str,
            width: int = 1200, height: int = 630, site_name: str = "Sift") -> str:
    def e(s: object) -> str:
        return escape(str(s), quote=True)
    return "\n".join([
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{e(site_name)}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(description)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(image)}">',
        f'<meta property="og:image:width" content="{int(width)}">',
        f'<meta property="og:image:height" content="{int(height)}">',
        f'<meta property="og:image:alt" content="{e(image_alt)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(description)}">',
        f'<meta name="twitter:image" content="{e(image)}">',
    ])
```
- [ ] **Step 4:** `uv run pytest tests/test_meta.py -q` → PASS.
- [ ] **Step 5: commit** `feat(meta): OG/Twitter static large-image card head block`.

---

## Task 6: `card.py` Pillow OG cards (best-effort)

**Files:** Create `src/sift/card.py`; Test `tests/test_card.py`.
**Interfaces — Produces:**
`render_static_card(path: Path) -> bool`,
`render_issue_card(path: Path, *, week: str, range_label: str, headline: str, category_counts: dict[str,int], story_count: int, feed_count: int) -> bool`.
Both return True on success, False (logged) on any failure. 1200×630 PNG.

- [ ] **Step 1: failing test** — `tests/test_card.py`:
```python
from pathlib import Path
from sift import card

def test_static_card_is_1200x630_png(tmp_path):
    out = tmp_path / "og.png"
    assert card.render_static_card(out) is True
    from PIL import Image
    with Image.open(out) as im:
        assert im.format == "PNG" and im.size == (1200, 630)

def test_issue_card_writes_png(tmp_path):
    out = tmp_path / "2026-26.png"
    ok = card.render_issue_card(out, week="2026-26", range_label="Jun 22–28, 2026",
        headline="GLM-5.2 beats Claude in cyber benchmarks",
        category_counts={"models_research": 4, "tooling": 2}, story_count=10, feed_count=20)
    assert ok is True and out.exists()

def test_card_best_effort_returns_false_without_pillow(tmp_path, monkeypatch):
    import builtins, importlib
    real = builtins.__import__
    def fake(name, *a, **k):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("no pillow")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    importlib.reload(card)
    assert card.render_static_card(tmp_path / "og.png") is False
    importlib.reload(card)  # restore
```
- [ ] **Step 2:** `uv run pytest tests/test_card.py -q` → FAIL.
- [ ] **Step 3:** create `src/sift/card.py` (imports PIL lazily inside functions so missing Pillow → caught; draws warm card with the spec palette). Concrete implementation:
```python
"""Generate the static-raster OG / cover cards (1200×630 PNG). Best-effort:
any failure (missing Pillow, missing font) logs and returns False so the weekly
run never breaks — callers fall back to the committed static og.png."""
from __future__ import annotations
import logging
from pathlib import Path

log = logging.getLogger("sift.card")

W, H = 1200, 630
BG = (27, 20, 16)          # #1b1410 warm umber
ACCENT = (224, 122, 79)    # #e07a4f
INK = (239, 231, 217)      # #efe7d9
MUTED = (173, 159, 133)    # #ad9f85
CAT_COLORS = {
    "models_research": (139, 132, 240), "tooling": (45, 212, 191),
    "infra": (245, 158, 11), "policy": (251, 113, 133), "business": (74, 222, 128),
}
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
MONO_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

def _font(candidates: list[str], size: int):
    from PIL import ImageFont
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _base():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=ACCENT)  # top accent rule
    d.text((72, 64), "SIFT", font=_font(FONT_CANDIDATES, 132), fill=INK)
    return img, d

def render_static_card(path: Path) -> bool:
    try:
        img, d = _base()
        d.text((76, 232), "Weekly AI signal — curated for one reader",
               font=_font(FONT_CANDIDATES, 44), fill=MUTED)
        d.text((76, 520), "one Claude call · everything else local & free",
               font=_font(MONO_CANDIDATES, 30), fill=ACCENT)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return True
    except Exception:  # noqa: BLE001 - best-effort; fall back to committed og.png
        log.exception("Static OG card generation failed")
        return False

def render_issue_card(path: Path, *, week: str, range_label: str, headline: str,
                      category_counts: dict[str, int], story_count: int,
                      feed_count: int) -> bool:
    try:
        img, d = _base()
        d.text((76, 224), f"WEEK {week}  ·  {range_label}",
               font=_font(MONO_CANDIDATES, 34), fill=ACCENT)
        head_font = _font(FONT_CANDIDATES, 54)
        y = 300
        for line in _wrap(d, headline, head_font, W - 150)[:3]:
            d.text((76, y), line, font=head_font, fill=INK)
            y += 64
        # category-mix bar
        total = sum(category_counts.values()) or 1
        x, bar_y, bar_w = 76, 520, W - 152
        for cat, n in category_counts.items():
            seg = int(bar_w * n / total)
            d.rectangle([x, bar_y, x + seg, bar_y + 26],
                        fill=CAT_COLORS.get(cat, MUTED))
            x += seg
        d.text((76, 566), f"{story_count} stories · {feed_count} feeds · one Claude call",
               font=_font(MONO_CANDIDATES, 28), fill=MUTED)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return True
    except Exception:  # noqa: BLE001
        log.exception("Issue OG card generation failed for %s", week)
        return False
```
- [ ] **Step 4:** `uv run pytest tests/test_card.py -q` → PASS.
- [ ] **Step 5: commit** `feat(card): best-effort Pillow OG/cover cards`.

---

## Task 7: digest redesign (`render.py`)

**Files:** Modify `src/sift/render.py`; Modify `src/sift/cli.py` (thread cost/site_url); Test `tests/test_render.py`.
**Interfaces — Consumes:** `weeks.week_range`, `urls.display_domain`/`safe_href`, `meta.og_tags`/`abs_url`, `config.site_url`. **Produces:** `build_digest(..., cost_usd: float | None = None)`, `render_html(digest, path, *, site_url, cost_usd=None)`.

- [ ] **Step 1: failing tests** — extend `tests/test_render.py`:
```python
def test_digest_html_has_static_image_og(tmp_path):
    digest = {"week": "2026-26", "stories": [_story()], "sources_scanned": [{"name":"X","count":3,"ok":True}]}
    out = tmp_path / "2026-26.html"
    render.render_html(digest, out, site_url="https://x.test/sift/", cost_usd=0.12)
    html = out.read_text()
    assert 'property="og:image" content="https://x.test/sift/digests/2026-26.png"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert "googleapis" not in html            # self-contained: no web fonts
    assert "20/20" not in html or "feeds" in html

def test_digest_shows_source_domain_chip(tmp_path):
    digest = {"week":"2026-26","stories":[_story(url="https://www.latent.space/p/x", source="Latent.Space")]}
    out = tmp_path / "w.html"; render.render_html(digest, out, site_url="https://x.test/sift/")
    assert "latent.space" in out.read_text()
```
(`_story()` helper returns a valid story dict with `links`, `score`, `category`, `summary`, `rationale`, `needs_verification`, `title`.)
- [ ] **Step 2:** `uv run pytest tests/test_render.py -q` → FAIL.
- [ ] **Step 3:** Rewrite `render.py`:
  - `render_html(digest, path, *, site_url, cost_usd=None)`: build `<head>` with the existing favicon + a new `meta.og_tags(...)` where `url = abs_url(site_url, f"digests/{week}.html")`, `image = abs_url(site_url, f"digests/{week}.png")`, `title = f"Sift — Week {week}"`, `description` = first story title (fallback tagline), `image_alt` = title.
  - Port the **system-font** dashboard markup/CSS from `.scratch/redesign-mockup.html` (Digest panel): metrics strip (`{count} stories · {live}/{total} feeds live[ · ${cost}]`), week-at-a-glance (category-mix bar + score mini-histogram, inline SVG/CSS, `aria-label`led), category-lane story rows with mono score badge, `needs verification` pill, and **source chips** built from `display_domain(link["url"])` + monogram, linking via `safe_href`. Use the spec token tables; map fonts to system stacks (`system-ui`/`ui-monospace`/Georgia).
  - `build_digest(...)` gains `cost_usd: float | None = None`; store it in the digest dict as `"cost_usd"` when provided.
  - Keep `render_json` unchanged.
- [ ] **Step 4:** In `cli.py` `cmd_run`: pass `cost_usd=breakdown.total_usd` to `build_digest`, and call `render.render_html(digest, html_path, site_url=cfg.site_url, cost_usd=breakdown.total_usd)`.
- [ ] **Step 5:** `uv run pytest tests/test_render.py tests/test_cli.py -q` → PASS.
- [ ] **Step 6: commit** `feat(render): dashboard digest, source chips, OG card head`.

---

## Task 8: site theme + OG + cards (`site.py`)

**Files:** Modify `src/sift/site.py`; Test `tests/test_site.py`.
**Interfaces — Consumes:** `weeks`, `meta`, `card`, `config.site_url`.

- [ ] **Step 1: failing tests** — extend `tests/test_site.py`:
```python
def test_prose_pages_have_static_og(tmp_path):
    pages = _build(tmp_path)  # existing helper that runs build_site
    idx = (tmp_path / "docs" / "index.html").read_text()
    assert 'property="og:image"' in idx and 'assets/og.png' in idx
    assert 'name="twitter:card" content="summary_large_image"' in idx
    assert 'property="og:url" content="https://' in idx

def test_build_site_writes_static_og_png(tmp_path):
    _build(tmp_path)
    assert (tmp_path / "docs" / "assets" / "og.png").exists()
```
- [ ] **Step 2:** `uv run pytest tests/test_site.py -q` → FAIL.
- [ ] **Step 3:** Modify `site.py`:
  - `_wrap(...)`/`_PAGE_TEMPLATE`: inject `meta.og_tags(...)` per page — `url = abs_url(cfg.site_url, <relative>)`, `image = abs_url(cfg.site_url, "assets/og.png")`, per-page title/description. Thread `cfg`/`site_url` into `_wrap` (add params). Add a skip-to-content link + `<main id="main">`.
  - Port the **web-font** dashboard theme tokens/CSS from `.scratch/redesign-mockup.html` into `SITE_CSS` (keep the existing Fraunces link; add Inter + JetBrains Mono families; apply the light + warm-dark token tables + category palette). Restyle the latest-issue hero + archive list to the dashboard look (mono meta, category accents; muted/labelled home stripe — not a multicolor SaaS gradient).
  - In `build_site`: write static card via `card.render_static_card(assets / "og.png")` (best-effort); in the archive loop, for each digest read its stories → `card.render_issue_card(out_dir / f"{week}.png", ...)` best-effort (headline = top-scored story title; category_counts from stories; feed_count from `sources_scanned`).
  - Use `weeks.week_range`/`week_end` (Task 1 already wired).
- [ ] **Step 4:** `uv run pytest tests/test_site.py -q` → PASS.
- [ ] **Step 5: commit** `feat(site): dashboard theme, OG head, per-issue cards`.

---

## Task 9: config files, deps, copy, regenerate, full suite

**Files:** `pyproject.toml`, `config.toml`, `config.example.toml`, `content/guide.md`, `content/sources.md`, regenerated `docs/**`.

- [ ] **Step 1:** `pyproject.toml`: move `pillow` from `[dependency-groups].dev` into `[project].dependencies` (e.g. `"pillow>=11.0"`). `uv sync`.
- [ ] **Step 2:** `config.toml` + `config.example.toml`: under `[sift]` add `site_url = "https://abhijitbansal.github.io/sift/"` and `boost = ["Ford"]` (example documents the field with a comment).
- [ ] **Step 3:** `content/guide.md` / `content/sources.md`: one line each documenting `boost` (watchlist up-weighting).
- [ ] **Step 4:** Regenerate: `uv run sift site`. Confirm `docs/assets/og.png`, `docs/digests/2026-26.png` exist; confirm OG tags + `summary_large_image` in `docs/index.html` and `docs/digests/2026-26.html`; confirm digest has no `googleapis`.
- [ ] **Step 5:** Full suite + coverage: `uv run pytest --cov=sift --cov-report=term-missing -q`. Coverage ≥80%.
- [ ] **Step 6: commit** `chore: pillow runtime dep, boost/site_url config, regenerate site`.

---

## Verification & deploy (post-plan)

- `uv run pytest --cov=sift -q` green, ≥80%.
- Open regenerated `docs/digests/2026-26.html` + `docs/index.html` in browser (light/dark, mobile).
- `grep` OG tags live after deploy; `og:image` returns `image/png` 200.
- Push branch, open PR, merge to `main` (admin-merge permitted). GitHub Pages serves new `docs/`.
- Final unfurl confirmation is a human paste into Teams.

## Self-review (planner)

- Spec coverage: unfurl (T5,T7,T8) · cards/graphics (T6,T7,T8) · theme (T7,T8) · source chips (T2,T7) · Ford boost (T3,T4) · weeks DRY (T1) · site_url (T3,T5,T7,T8) · deps/config/copy (T9). No gaps.
- Placeholders: none — concrete code given for all logic modules; CSS port references the committed mockup artifact (a real file, not a vague placeholder).
- Type consistency: `week_end`/`week_range`, `display_domain`, `og_tags`/`abs_url`, `render_issue_card`/`render_static_card`, `build_digest(cost_usd=)`, `render_html(site_url=, cost_usd=)` used consistently across tasks.
