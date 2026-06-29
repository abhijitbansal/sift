# Sift v2 — Design

**Status:** approved 2026-06-28
**Branch:** `feat/sift-v2`

## Intent

Take Sift from "built but never run" to a tool used weekly, and add an all-in-one
GitHub Pages site (explainer + usability guide + roadmap + live digest archive)
that doubles as a living document of the work and plans before the repo goes public.

Sift's ethos is preserved throughout: **one Claude API call per weekly run,
everything else local and free, minimal dependencies, secrets in the keychain.**

## Scope — 4 phases, each shippable

| Phase | Theme | Outcome |
|---|---|---|
| 1 | Harden | Robust API call, cost tracking, full test coverage, first real run |
| 2 | Capabilities | Tuning controls + SMTP email delivery |
| 3 | Site | Static-site generator, digests under `docs/`, archive index, prose pages, Pages live |
| 4 | Public-ready | CI, README refresh, contributor/security docs, secret-scan preflight, manual checklist |

## Patterns to mirror (existing code)

| Category | Source | Pattern |
|---|---|---|
| Naming | `src/sift/fetch.py` | `snake_case` funcs, `UPPER_SNAKE` consts, frozen dataclasses |
| Errors | `src/sift/fetch.py:74` | dead feed logged + skipped, never fatal; raise `ValueError` at config boundary |
| Logging | `src/sift/cli.py:24` | `logging.getLogger("sift.<module>")`, info on counts |
| Data access | `src/sift/store.py` | `sqlite3` with `executescript` schema, context-managed `connect()` |
| Tests | `tests/test_fetch.py` | pytest, AAA, inline RSS fixtures, `parse_entry`-style unit tests |

## Module map

### Phase 1 — Harden
- `src/sift/rank.py` (UPDATE): adaptive thinking (`thinking={"type":"adaptive"}`);
  handle `stop_reason` `refusal` and `max_tokens`; stream via
  `client.messages.stream(...).get_final_message()`; return `(stories, usage)`.
- `src/sift/cost.py` (CREATE): per-model price table (Opus 4.8 = $5/$25 per 1M),
  `usage_cost(model, usage) -> CostBreakdown`.
- `src/sift/store.py` (UPDATE): extend `digests` table with `model`,
  `input_tokens`, `output_tokens`, `cost_usd`; add `digest_history()` reader.
- `tests/`: `test_cost.py`, `test_rank.py` (mocked client), `test_store.py`.

### Phase 2 — Capabilities
- `src/sift/config.py` (UPDATE): `Feed.weight` (default 1.0); `[sift] min_score`,
  `mute` (list); `[email]` block (`enabled`, `host`, `port`, `from`, `to`,
  `use_tls`); password from keychain `SIFT_SMTP_PASSWORD`.
- `src/sift/filters.py` (CREATE): `apply_min_score`, `apply_source_weight`
  (mechanical post-rank). Mute is semantic — fed to the prompt.
- `src/sift/deliver.py` (CREATE): `send_digest(cfg, html, week)` over stdlib
  `smtplib`/`email`; boundary validation; never log the password.
- `src/sift/rank.py` (UPDATE): thread `mute` + per-feed `weight` hints into prompt.
- `tests/`: `test_filters.py`, `test_config.py`, `test_deliver.py` (mock SMTP).

### Phase 3 — Site
- `docs/assets/sift.css` (CREATE): the digest aesthetic (serif, dark-mode,
  terracotta), extracted from `render.py`'s inline `<style>` — single source.
- `src/sift/render.py` (UPDATE): link the shared CSS; write digests to
  `docs/digests/YYYY-WW.{html,json}`.
- `src/sift/site.py` (CREATE): render `index/guide/roadmap` from `content/*.md`;
  rebuild `docs/digests/index.html` archive from digest history.
- `content/{index,guide,roadmap}.md` (CREATE): prose sources.
- `src/sift/cli.py` (UPDATE): `sift site` (rebuild), `sift email <week>`,
  `sift history`; wire deliver + site into `run`.
- `tests/`: `test_site.py`, `test_render.py`, `test_cli.py`.

### Phase 4 — Public-ready
- `.github/workflows/ci.yml` (CREATE): `uv run pytest` on push/PR.
- `README.md` (UPDATE), `CONTRIBUTING.md` + `SECURITY.md` (CREATE).
- Secret scan (working tree + history) before go-public.
- `.scratch/sift-v2-test-checklist.html` (CREATE): interactive manual-test checklist.

## Key decisions
- **Delivery: SMTP**, app password in keychain `SIFT_SMTP_PASSWORD`, `[email].enabled`
  toggle. No new dependency.
- **Tuning: config-driven & immutable.** `weight` (prompt hint + mechanical score
  multiplier), `min_score` (mechanical cutoff), `mute` (semantic, prompt-fed).
- **Digests move to `docs/digests/`** so the archive is the site. `.gitignore`,
  README, launchd updated.
- **Pages from `main` → `/docs`** (GitHub Pro + private repo). Until enabled, the
  site is viewable by opening `docs/index.html`.
- **Site tech: custom Python static generator + one shared CSS** (not MkDocs):
  unified aesthetic, minimal deps, true to the project ethos. One small dep
  (`markdown`) renders the prose pages.

## Dependencies / risks
| Risk | Mitigation |
|---|---|
| `ANTHROPIC_API_KEY` absent from keychain | First real run is a manual step; `--dry-run` verifies everything up to the call |
| SMTP password absent | Email send is a manual verify step; unit tests mock SMTP |
| Pages needs Pro toggle | Prep `docs/` + exact enable steps; site works locally meanwhile |
| Secrets in history before going public | Hard gate: working-tree + git-history scan before `gh repo edit --visibility public` |

## Acceptance
1. `pytest` ≥80% green; `rank` survives refusal/truncation; `sift history` shows cost; one real digest committed *(blocked on key)*.
2. Sub-`min_score` story dropped; weighted source reorders; `sift email <week>` lands in inbox *(blocked on SMTP secret)*.
3. `sift site` builds `docs/`; archive lists all digests; three prose pages render; Pages serves them.
4. CI green on PR; README current; secret-scan clean; manual checklist delivered.
