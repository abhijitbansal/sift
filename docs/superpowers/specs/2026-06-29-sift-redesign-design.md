# Sift redesign — design spec

**Date:** 2026-06-29
**Status:** approved (visual mockup reviewed; warm-dark palette confirmed)
**Mockup:** `.scratch/redesign-mockup.html` (gitignored)

## Goals

1. Replace the editorial-serif "RSS feel" with a **tech-brief / dashboard** look — dense,
   metric-forward, scannable — while staying warm and distinctive (not generic-AI/SaaS).
2. Keep everything **mobile-first** and **light/dark**; keep the weekly digest **self-contained**
   (single file, no external CSS/JS, offline- and email-safe).
3. **Up-weight watched entities** (Ford first) so they surface more reliably in the ranking.
4. **Fix Teams/Slack link unfurl** for text *and* image (our own pages must render a titled,
   large-image card when shared).
5. **List the real source** per story as a favicon-style chip, richer than today's plain
   "Covered by" line.

## Source of truth (research Step 1) — verified

Sift is **self-contained, edit-in-place**: GitHub Pages serves committed `docs/` from `main`.
The generator (`src/sift/site.py`, `src/sift/render.py`) writes `docs/`. The `~/projects/sift-publish`
clone is only the cron *executor* (pull → run → push), not a separate source. **All edits happen in
this repo**, then `sift site` / `sift run` regenerates `docs/`, commit.

---

## 1. Unfurl fix (evidence-backed)

Live `<head>` diff (2026-06-29) of the known-good `abhijitbansal.github.io/claude-skills/` vs ours:

- **claude-skills (works):** full OG block + `og:image` = **static `og.png` 2400×1260** with
  **`og:image:width`/`og:image:height`** + `og:image:alt`, and `twitter:card=summary_large_image`
  + `twitter:title/description/image`. **No JSON-LD, no canonical, no oEmbed.**
- **sift (broken):** **zero** `og:`/`twitter:` tags.

**Conclusion:** the single real trigger for Teams' titled-link upgrade is a **qualifying static-raster
large-image card** — a PNG/JPG `og:image` with declared width/height + `twitter:card=summary_large_image`.
The research's secondary hypothesis (canonical/oEmbed/JSON-LD) is **falsified** by the known-good page.
SVG or animated-GIF og:images, or missing dimensions, do **not** qualify.

**Head block to add to every page** (both `_PAGE_TEMPLATE` in `site.py` and `_PAGE` in `render.py`):

```
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sift">
<meta property="og:title" content="{page title}">
<meta property="og:description" content="{page description}">
<meta property="og:url" content="{absolute https url, per-page, trailing slash on index}">
<meta property="og:image" content="{absolute https PNG url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{page title}">
<meta name="twitter:description" content="{page description}">
<meta name="twitter:image" content="{same absolute https PNG url}">
```

- `og:image` is the **per-issue card** for digest pages (`digests/<week>.png`) and the **static
  `og.png`** for prose pages. Both are 1200×630 PNGs.
- New config `site_url` (default `https://abhijitbansal.github.io/sift/`) builds the absolute
  `og:url`/`og:image` URLs. Per-page `og:url` = `site_url` + relative path.
- No JSON-LD / canonical added (proven unnecessary by the known-good page).

## 2. OG / cover-card generator — new `src/sift/card.py` (Pillow)

- **Per-issue card** → `docs/digests/<week>.png` (1200×630): dark warm-terracotta background, **SIFT**
  wordmark, `WEEK YYYY-WW · {range}`, the #1 headline, a category-mix mini-bar, footer line
  `N stories · M feeds · one Claude call`. Becomes that digest's `og:image`/`twitter:image`.
- **Static site card** → `docs/assets/og.png` (committed): "Sift — weekly AI signal" + tagline + mark.
  og:image for all prose pages **and the universal fallback** if Pillow/fonts are unavailable.
- Reuses `scripts/gen_favicons.py`'s font-candidate chain (Georgia/Times/DejaVu → `load_default`).
- **Best-effort:** any generation failure logs and falls back to the static `og.png`; the run never
  breaks (same ethos as `_maybe_rebuild_site`).

**Fork decision — Pillow becomes a runtime dependency** (currently dev-only). Per-issue cards must
render during the weekly `sift run`. Small, already used, cron runs on the user's Mac via uv.
A committed static `docs/assets/og.png` guarantees a valid og:image even if Pillow is absent.

## 3. Theme — tech-brief / dashboard

**Type system**
- **Display / wordmark:** Fraunces — wordmark + big page/section titles **only** (brand anchor).
- **Body / UI:** Inter (site) / `system-ui` stack (digest fallback).
- **Data** (scores, week-ids, counts, category tags, metrics): JetBrains Mono / `ui-monospace`.

**Fork decision — fonts:** the **site** loads Fraunces/Inter/JetBrains Mono from Google Fonts (as it
already loads Fraunces); the **weekly digest** uses **system stacks only** (no web fonts) so it stays
offline- and email-safe. System fallbacks: display→`Georgia, "Times New Roman", serif`;
body→`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; data→`ui-monospace, "SF Mono", Menlo, Consolas, monospace`.

**Color tokens** (from the approved mockup):

Light:
```
--bg:#f7f3ea  --surface:#fffdf7  --surface-2:#f1ead9  --surface-3:#ece3cf
--text:#241f18  --text-2:#473f33  --muted:#6c6353  --line:#e5dcc8  --line-2:#d3c8b0
--accent:#b4542e  --accent-2:#9a4322  --accent-ink:#fff7f1  --badge-ink:#ffffff  --live:#15803d
```
Dark (warm umber — confirmed):
```
--bg:#1b1410  --surface:#241b14  --surface-2:#2d2218  --surface-3:#36291d
--text:#efe7d9  --text-2:#d2c6af  --muted:#ad9f85  --line:#3b2d20  --line-2:#4c3a29
--accent:#e07a4f  --accent-2:#ef9067  --accent-ink:#1a0f08  --badge-ink:#1b1410  --live:#4ade80
```
Category palette (light / dark) — used on score badge, tag, glance bar, lane rail, cover card:
```
models_research "Models & Research"  #5b54d6 / #8b84f0   (indigo)
tooling         "Tooling"            #0d9488 / #2dd4bf   (teal)
infra           "Infra"              #b45309 / #f59e0b   (amber)
policy          "Policy"             #be123c / #fb7185   (rose)
business        "Business"           #15803d / #4ade80   (green)
```
Terracotta `--accent` stays the brand/primary; category colors are secondary. Category-name/tag text
must use **dark ink + a color swatch** (not small color-on-tint), verified ≥4.5:1 in both themes.

## 4. Digest redesign (`render.py`)

Self-contained single file. In order:

1. **Header** — SIFT wordmark + `Week 2026-26 · Jun 22–28, 2026` + mono **metrics strip**
   `10 stories · 20/20 feeds live · $0.12`.
2. **Week at a glance** — pure-CSS/inline-SVG, `aria`-labelled, no raster: a **stacked category-mix
   bar** with legend, and a **score-spread mini histogram** (`hi 9 · lo 5 · avg 7.0`).
3. **Stories** — grouped by category lane (colored left rail) **and** a "by score" reading toggle
   (#1–#10 global rank). Each story: mono **score badge** (category-colored), title link, two-sentence
   summary, muted-italic rationale (`›` marker), `needs verification` pill where flagged, **source chips**.
4. **Source chips** — favicon-style: colored monogram square (domain initial, curated warm palette,
   white letter ≥4.5:1) + real domain text (via new `urls.display_domain()`), linking to the source
   URL through `safe_href`. No remote fetch → stays offline/email-safe.
5. **Sources scanned** — compact chip grid `name count`; zero/dead feeds (e.g. arXiv cs.AI 0) noted.
6. **Footer** — unchanged ethos line. Full OG head block + per-issue `og:image`.

`render_html` gains the data it needs: week **range** + **cost_usd** + **site_url**. Cost is threaded
from `cmd_run` (`breakdown.total_usd`) into the digest dict (`build_digest` gains an optional
`cost_usd`); range comes from the shared `weeks.py` helper.

## 5. Site pages (`site.py`)

Same tokens; editorial masthead kept but tightened. Home latest-issue hero restyled as a dashboard
card (the home gradient stripe stays muted/labelled or becomes a single terracotta rule — avoid the
multicolor-SaaS tell). Archive list gets the mono/category treatment. OG head block (static `og.png`)
on all prose pages. Skip-to-content link added.

## 6. Ford up-weight (prompt-only)

- New `[sift] boost = ["Ford"]` → parsed as `boost: tuple[str, ...]` in `config.py`.
- `rank.build_prompt` gains a line (mirroring the mute/weight-hint pattern), only when `boost` is set:
  > "Strongly prioritize stories about these entities/topics — raise their importance score by ~2
  > points and surface them even when borderline: {boost joined}."
- No code-side score mutation, no guaranteed lane (user chose "up-weight in prompt only").
- `config.example.toml` documents `boost`; `config.toml` seeds `["Ford"]`.

## 7. Shared cleanup (DRY)

Extract `_week_end` / `_week_range` from `site.py` into new `src/sift/weeks.py`, shared by `site.py`
and `render.py` (removes duplication the redesign would otherwise create).

---

## Files touched

| File | Change |
|---|---|
| `src/sift/render.py` | OG head block; dashboard digest (metrics strip, glance viz, lanes + score toggle, source chips); per-issue og:image; thread range/cost/site_url |
| `src/sift/site.py` | OG head block; theme tokens/CSS overhaul; dashboard home/archive; static og.png; skip link; thread site_url; use `weeks.py` |
| `src/sift/card.py` *(new)* | Pillow OG/cover-card generator (per-issue + static), best-effort |
| `src/sift/weeks.py` *(new)* | shared `week_end`/`week_range` helpers |
| `src/sift/config.py` | add `boost: tuple[str,...]` and `site_url: str` |
| `src/sift/rank.py` | boost hint in `build_prompt` |
| `src/sift/urls.py` | add `display_domain(url)` |
| `config.toml` / `config.example.toml` | add `boost`, `site_url` |
| `pyproject.toml` | move Pillow dev→runtime dep |
| `content/*.md` | light copy (mention boost in guide; sources) |
| `docs/assets/og.png` *(new, committed)* | static fallback card |
| `docs/**` | regenerated output |

## Test plan (keep ≥80%; currently 93%)

- **`tests/test_weeks.py`** *(new)* — `week_end`/`week_range` incl. unparseable inputs.
- **`tests/test_card.py`** *(new)* — card writes a valid PNG of declared size; best-effort fallback
  when Pillow/font missing (monkeypatch import) returns gracefully; per-issue + static paths.
- **`tests/test_config.py`** — `boost` parsing (default empty, list of strings, whitespace strip);
  `site_url` default + override.
- **`tests/test_rank.py`** — `build_prompt` includes the boost line iff `boost` set; omitted otherwise.
- **`tests/test_urls.py`** — `display_domain` (strip `www.`, ports, paths; non-http → "").
- **`tests/test_render.py`** — OG tags present with absolute URLs + dimensions; `twitter:card`
  = summary_large_image; metrics strip + glance + source chips render; offline (no `googleapis`).
- **`tests/test_site.py`** — OG tags on prose pages; per-page absolute `og:url`; static og.png ref;
  shared `weeks` wiring.

## Verification (research Step 4)

After implementing + `sift site`/`sift run`: re-fetch the live page, confirm the new tags are present
and `og:image` returns HTTP 200 `image/png`. Final confirmation is a human pasting a digest URL into
Teams. Commit: `fix(meta): Teams titled-link preview — static og:image + dimensions`.

## Decisions log

- Vibe: tech-brief / dashboard. Ford: up-weight in prompt only. Graphics: per-issue cover card +
  source favicon chips + week-at-a-glance viz + category color/icons. Unfurl: own-page OG fix +
  rich source chips.
- Fonts: web on site, system-stack on digest. Pillow: runtime dep, best-effort fallback.
- Dark background: warm umber `#1b1410` ramp (user-confirmed).
