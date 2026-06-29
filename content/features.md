# Features

Everything Sift does, grouped by what it's for. Each line names the command or
config knob that drives it.

## Curation

- **Multi-feed fetch** — any number of RSS/Atom feeds. `sift add <url>` validates a
  feed before adding it; `sift list` shows them all.
- **Seen-once memory** — every URL ever shown is remembered in SQLite, so a story
  never appears in two digests.
- **Freshness window** — items older than eight days are dropped automatically.
- **Free local dedup** — near-identical headlines from different feeds collapse
  into one cluster before anything is sent to the model.
- **One-call ranking** — a single Claude call merges remaining duplicates,
  categorizes (models &amp; research / tooling / infra / policy / business), scores
  importance 1–10, and writes a two-sentence neutral summary per story.
- **Primary-source flag** — any story whose central claim isn't from a primary
  source (official blog, paper, announcement) is marked *needs verification*.

## Tuning &amp; control (all in `config.toml`)

- **Interest profile** — a paragraph of plain language describing your signal vs.
  noise; it drives every score.
- **Per-feed weight** — `weight = 2.0` floats a trusted source's stories up
  (a score multiplier, plus a trust hint to the model).
- **Minimum score** — `min_score` drops weak stories before the digest's item cap.
- **Muted topics** — `mute = [...]` tells the model to down-rank or exclude
  subjects you never want to see.
- **Item cap** — `max_items_per_digest` keeps only the top-scored N.
- **Model choice** — `model` is any current Anthropic id (Opus for quality, Sonnet
  for cheaper runs).

## Delivery

- **Self-contained HTML digest** — dark-mode-friendly, opens anywhere, no external
  assets, written to `docs/digests/`.
- **JSON digest** — the same data as machine-readable JSON for anything downstream.
- **Email** — `[email] enabled = true` sends each digest over SMTP; re-send any
  past week with `sift email <week>`. The password is read from the keychain,
  never stored or logged.
- **Live site archive** — every digest is browsable from the site's archive index.

## Observability &amp; cost

- **Exact per-run cost** — token counts and USD are computed from the model's
  pricing and stored per run.
- **Run history** — `sift history` lists every run with tokens, cost, and a running
  total.
- **Full logging** — `logs/sift.log` records counts and errors for every step.
- **Free dry-run** — `sift run --dry-run` runs the whole pipeline up to (but not
  including) the API call and prints exactly what would be sent — $0.

## The site

- **All-in-one** — explainer, this feature list, the [how-it-works](how-it-works.html)
  flow + architecture, a usage [guide](guide.html), the [roadmap](roadmap.html),
  and the digest archive.
- **One visual language** — a single shared stylesheet; the digests match it but
  stay self-contained.
- **Generated from the pipeline** — `sift run` rebuilds the site automatically;
  `sift site` rebuilds it on demand.
- **GitHub Pages–ready** — served from `main` / `/docs`.

## Operations

- **Scheduled runs** — a launchd plist runs the pipeline weekly (Sunday 6am) and
  reads secrets from the keychain at run time.
- **Resilient** — a dead feed, a failed email, or a site-rebuild error is logged
  and skipped; the digest is never lost.
- **Schema migration** — the SQLite history migrates itself forward in place, so
  old databases keep working.

## Quality

- **Tested** — unit + integration tests across the pipeline, with an 80% coverage
  gate enforced in CI.
- **Reviewed** — the v2 changes went through a multi-agent adversarial review.
- **Secrets stay out of git** — keychain-only secrets, verified by a working-tree
  and full-history scan before going public.
