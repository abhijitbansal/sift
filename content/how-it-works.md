# How Sift works

Sift turns a firehose of AI feeds into a two-minute weekly read. The whole design
follows one rule: **do everything possible locally and for free, and spend exactly
one Claude API call per week** — on the one step that actually needs judgment.

## The pipeline

<!--sift:pipeline-->

## Architecture

Sift is a handful of small, single-purpose Python modules, each independently
testable. Business logic is separated from the I/O boundaries (network, the API
call, SMTP, the filesystem) so the logic is unit-tested and the boundaries are
mocked.

| Module | Responsibility |
|---|---|
| `config.py` | Load + validate `config.toml` into immutable dataclasses (feeds, weights, mute, min_score, email) |
| `fetch.py` | Fetch feeds, normalize entries to a common `Item`; a dead feed is logged, not fatal |
| `dedup.py` | Greedy title-similarity clustering of near-duplicate items |
| `rank.py` | The single Claude call: merge / categorize / score / summarize, as validated JSON |
| `filters.py` | Mechanical post-rank source weighting and the min-score cutoff |
| `render.py` | Build the digest and render self-contained HTML + JSON |
| `site.py` | Generate the static site (explainer, guide, roadmap, archive) |
| `deliver.py` | Email the digest over SMTP, password from the keychain |
| `cost.py` | Per-model price table → the USD cost of a run |
| `store.py` | SQLite history: seen URLs, and one row per run with tokens + cost |
| `cli.py` | Wire it together; the `run` / `add` / `list` / `email` / `history` / `site` commands |

## What persists

- **`sift.db`** (SQLite, local, gitignored) — every URL ever seen (so nothing is
  shown twice) and one row per run with its token counts and cost.
- **`docs/digests/`** (committed) — each week's HTML + JSON digest, and the
  archive index. This is what the site serves.
- **`logs/sift.log`** (local, gitignored) — counts and errors for every step.

Secrets live only in the macOS keychain (or env vars) — never in the repo.

## Design principles

- **One paid call.** The expensive judgment — what matters, what's a dupe, how to
  summarize — is exactly one Claude call. Fetching, filtering, dedup, rendering,
  history, email, and the site are all local and free.
- **Local-first &amp; offline-friendly.** History is a local SQLite file; digests are
  self-contained HTML that open anywhere.
- **Minimal dependencies.** Standard library wherever possible (`smtplib`,
  `sqlite3`, `tomllib`); a small handful of focused libraries otherwise.
- **Immutable data.** Functions build new objects rather than mutating inputs.
- **Fail soft on the edges.** A dead feed, a failed email, or a site-rebuild hiccup
  never costs you the digest — they're logged and the run continues.
- **One reader.** The interest profile and digest are tuned for one person by
  design; that's the point, not a limitation.

## Cost

A typical week is a few thousand input tokens and a couple thousand output —
cents per run on Opus, less on Sonnet. `sift history` shows the exact running
total. See the [features](features.html) page for the full capability list and
the [guide](guide.html) to set it up.
