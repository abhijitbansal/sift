# Sift

A weekly AI-news curation pipeline for one reader. Fetches RSS/Atom feeds,
drops what you've already seen, clusters obvious duplicates locally for free,
then makes **one** Claude API call to merge, categorize, score, and summarize —
and renders a clean, dark-mode-friendly HTML digest. Optionally emails it to you
and publishes a browsable archive.

> **Live site:** https://abhijitbansal.github.io/sift/ — explainer, usage guide,
> roadmap, the digest archive, and a JSON API for AI agents (see below). Built
> from [`docs/`](docs/index.html) and published via GitHub Pages from `main`.

## Quickstart

1. **Install** (requires [uv](https://docs.astral.sh/uv/) and Python 3.11+):

   ```sh
   git clone <repo-url> sift && cd sift
   uv sync
   ```

2. **Store your API key in the keychain** (never in the config or repo):

   ```sh
   security add-generic-password -s ANTHROPIC_API_KEY -a "$USER" -w
   ```

3. **Configure** — copy `config.example.toml` to `config.toml` and edit feeds,
   model, interest profile, and the optional tuning/email settings.

4. **Run**:

   ```sh
   export ANTHROPIC_API_KEY="$(security find-generic-password -s ANTHROPIC_API_KEY -w)"
   uv run sift run
   open docs/digests/*.html
   ```

## Commands

| Command | What it does |
|---|---|
| `uv run sift run` | Full pipeline: fetch → filter → dedup → one API call → render → record → email → site |
| `uv run sift run --dry-run` | Everything except the API call; prints what would be sent |
| `uv run sift add <feed-url>` | Validate a feed URL resolves, then append it to `config.toml` |
| `uv run sift add-x <handle>` | Add an X handle via the configured `[x]` RSS bridge |
| `uv run sift list` | List configured feeds (with weights) |
| `uv run sift email <week>` | Re-send a rendered digest, e.g. `sift email 2026-26` |
| `uv run sift history` | Show every run with token counts and cost |
| `uv run sift site` | Rebuild the static site under `docs/` |

Digests land in `docs/digests/YYYY-WW.{html,json}`. History (and per-run cost)
lives in `sift.db`; logs in `logs/sift.log`. A dead feed never kills the run —
it's logged and skipped.

## Steering the digest

All in `config.toml`:

- **`interest_profile`** — a paragraph of what you consider signal vs. noise.
- **feed `weight`** — float per feed (default 1.0); floats trusted sources up.
- **`min_score`** — 1–10 cutoff; weak stories are dropped before the cap.
- **`mute`** — topics the model should down-rank or exclude.

## Email delivery (optional)

Set `[email] enabled = true` in `config.toml` and store the SMTP password:

```sh
security add-generic-password -s SIFT_SMTP_PASSWORD -a "$USER" -w
```

## Run weekly via launchd (Sunday 6am)

```sh
cp launchd/com.abhijitbansal.sift.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.abhijitbansal.sift.plist
launchctl start com.abhijitbansal.sift   # test it immediately
```

The plist reads the keychain secrets at run time and schedules **Sunday 06:00 in
the machine's local timezone**. After a successful run it commits the new digest
under `docs/` and `git push`es, so the GitHub Pages site rebuilds automatically.
A week with nothing new writes no digest, so nothing is committed.

Logs: `/tmp/com.abhijitbansal.sift.out.log` and `.err.log`.

### Requirements for the auto-publish to work

The job runs `cd ~/projects/sift && uv run sift run && git add -A docs && git commit && git push`. For that to actually update the live site:

- **The checkout must be on `main` at run time.** The job pushes whatever branch
  is currently checked out, and Pages serves `main`. If you leave a feature
  branch checked out at Sunday 06:00, the digest pushes to the wrong branch and
  the site won't update. Either return to `main` before the weekend, or run the
  schedule from a **separate clone dedicated to publishing** (recommended if you
  develop in this same directory).
- **Push must work non-interactively.** The remote is SSH; verify with
  `ssh -o BatchMode=yes -T git@github.com` (should greet you by name). If your key
  has a passphrase, add it once: `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`.
- **`main` branch protection must keep admins exempt.** The push goes straight to
  the protected `main` branch and relies on the owner's admin bypass
  (`enforce_admins=false`). Do **not** enable "Include administrators", or the
  weekly push is rejected.
- The Mac must be awake at the scheduled time (launchd runs a missed job on the
  next wake).

## For AI agents (JSON API)

A new digest publishes every **Sunday**. The live site exposes a machine-readable
JSON API — scrape it politely (it changes once a week):

| Endpoint | What |
|---|---|
| [`/llms.txt`](https://abhijitbansal.github.io/sift/llms.txt) | How to scrape + the digest JSON schema |
| [`/digests/index.json`](https://abhijitbansal.github.io/sift/digests/index.json) | Manifest of every week (week, range, story count, cost, html/json URLs, `latest`) |
| [`/digests/latest.json`](https://abhijitbansal.github.io/sift/digests/latest.json) | The newest digest in full, at a stable URL |
| `/digests/<YYYY-WW>.json` | Any specific ISO-week digest, e.g. `/digests/2026-26.json` |

Each digest lists scored, categorized stories with a two-sentence summary, source
links, and a `needs_verification` flag. Weeks are ISO year-week (UTC), labeled by
the week the digest covers (ending that Sunday). These files are generated by
`sift site`; the archive scanner ignores the reserved `index`/`latest` stems.

## Tests

```sh
uv run python -m pytest
uv run python -m pytest --cov=sift   # with coverage
```

## Cost

One API call per weekly run (model set in `config.toml`, default
`claude-opus-4-8`). Everything else — fetching, dedup, rendering, history, the
email, the site — is local and free. `sift history` shows the running total.

## License

MIT — see [LICENSE](LICENSE).
