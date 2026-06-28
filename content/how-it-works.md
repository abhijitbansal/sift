# How Sift works

Sift turns a firehose of AI feeds into a two-minute weekly read. The whole design
follows one rule: **do everything possible locally and for free, and spend exactly
one Claude API call per week** — on the one step that actually needs judgment.

## The pipeline

<div class="flow">
  <div class="stage"><h4>1 · Fetch</h4><p>Pull every configured RSS/Atom feed over HTTP. A dead or slow feed is logged and skipped — it never kills the run.</p><span class="mod">fetch.py</span></div>
  <div class="arrow">↓</div>
  <div class="stage"><h4>2 · Filter</h4><p>Drop anything already seen (tracked in SQLite) or older than eight days. Most of the firehose disappears here, for free.</p><span class="mod">cli.py · store.py</span></div>
  <div class="arrow">↓</div>
  <div class="stage"><h4>3 · Dedup</h4><p>Cluster near-identical headlines with local string similarity, so the same story from five feeds collapses into one cluster.</p><span class="mod">dedup.py</span></div>
  <div class="arrow">↓</div>
  <div class="stage paid"><h4>4 · Rank — the one API call</h4><p>A single Claude call merges clusters that still cover the same story, assigns a category, scores importance 1–10 against your interest profile, writes a two-sentence summary, and flags non-primary-source claims. Structured JSON output, adaptive thinking.</p><span class="mod">rank.py · model from config.toml (the only paid step)</span></div>
  <div class="arrow">↓</div>
  <div class="stage"><h4>5 · Weight &amp; cut</h4><p>Apply per-feed trust weights and drop anything below your <code>min_score</code>, then keep the top N.</p><span class="mod">filters.py</span></div>
  <div class="arrow">↓</div>
  <div class="stage"><h4>6 · Render</h4><p>Write a self-contained HTML digest (and JSON) into the site's archive. Self-contained so it also works in email and offline.</p><span class="mod">render.py → docs/digests/</span></div>
  <div class="arrow">↓</div>
  <div class="stage"><h4>7 · Record, deliver, publish</h4><p>Record the run and its exact cost, optionally email the digest, and rebuild this site so the new week shows in the archive.</p><span class="mod">store.py · deliver.py · site.py</span></div>
</div>

Everything except step 4 is local and free.

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
