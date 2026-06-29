# Signal, not noise

A weekly AI-news curation pipeline for one reader.

Sift fetches the AI feeds you care about, throws away what you've already seen,
clusters obvious duplicates locally for free, then makes **one** Claude API call
to merge, categorize, score, and summarize the week — and renders a clean,
dark-mode-friendly digest you can read in two minutes.

It is deliberately small: one API call per week, everything else local and free.

## Why it exists

The firehose of AI news is mostly noise: press-release vapor, chatbot drama,
incremental product marketing. Sift is built for a reader who wants **signal** —
real deployments, concrete numbers, primary sources — and who would rather spend
two minutes on a curated digest than an hour doom-scrolling feeds.

You describe what you care about once, in plain language. Sift scores every story
against that profile and keeps only the top handful.

## How it works

The pipeline is five steps, and only one of them costs anything:

1. **Fetch** — pull every configured RSS/Atom feed. A dead feed is logged and
   skipped, never fatal.
2. **Filter** — drop anything already seen (tracked in a local SQLite database)
   or older than eight days.
3. **Dedup** — cluster near-identical headlines locally with string similarity,
   so the same story from five feeds becomes one cluster. Free.
4. **Rank** — the single Claude call. It merges clusters that still cover the
   same story, assigns a category, scores importance 1–10 against your interest
   profile, writes a two-sentence neutral summary, and flags any story whose
   central claim isn't from a primary source.
5. **Render & deliver** — write a self-contained HTML digest (and JSON), record
   the run and its cost, optionally email it to you, and update this site's
   archive.

## What you steer

- **Interest profile** — a paragraph describing your signal vs. noise.
- **Feed weights** — trust some sources more than others.
- **Minimum score** — drop weak stories even when the digest isn't full.
- **Muted topics** — tell Sift what you never want to see.

See the [usage guide](guide.html) to set it up, and the
[roadmap](roadmap.html) for where it's headed.

## Cost

One Claude API call per weekly run. Everything else — fetching, dedup, rendering,
history, the email, this site — is local and free. A typical week costs a few
cents; `sift history` shows the exact running total.

## For AI agents

A new digest publishes every **Sunday**. Sift exposes a machine-readable JSON API
you are welcome to scrape — politely, since it only changes once a week:

- [`llms.txt`](llms.txt) — how to scrape, plus the digest JSON schema.
- [`digests/index.json`](digests/index.json) — manifest of every week (week id,
  date range, story count, cost, and the HTML/JSON URL for each).
- [`digests/latest.json`](digests/latest.json) — the newest digest, in full, at a
  stable URL.
- `digests/<YYYY-WW>.json` — any specific ISO-week digest (e.g.
  `digests/2026-26.json`).

Each digest JSON lists scored, categorized stories with a two-sentence summary,
the source links, and a `needs_verification` flag. Weeks are ISO year-week (UTC),
labeled by the week the digest covers.
