# Sift

A weekly AI-news curation pipeline for one reader. Fetches RSS/Atom feeds,
drops what you've already seen, clusters obvious duplicates locally for free,
then makes **one** Claude API call to merge, categorize, score, and summarize —
and renders a clean, dark-mode-friendly HTML digest. Optionally emails it to you
and publishes a browsable archive.

> Full explainer, usage guide, and roadmap: the site under [`docs/`](docs/index.html)
> (served via GitHub Pages once the repo is public). Open `docs/index.html`
> locally in the meantime.

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

The plist reads the keychain secrets at run time and schedules Sunday 06:00 in
the machine's local timezone. After a successful run it commits the new digest
under `docs/` and pushes, so the GitHub Pages site updates automatically. For the
push to publish, the repo must be checked out on the branch Pages serves (`main`)
with a clean working tree, and launchd needs push credentials — add your SSH key
to the keychain once with:

```sh
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

A week with nothing new writes no digest, so nothing is committed.

Logs: `/tmp/com.abhijitbansal.sift.out.log` and `.err.log`.

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
