# Sift

A weekly AI-news curation pipeline for one reader. Fetches RSS/Atom feeds,
drops what you've already seen, clusters obvious duplicates locally for free,
then makes **one** Claude API call to merge, categorize, score, and summarize —
and renders a clean dark-mode-friendly HTML digest.

## Quickstart

1. **Install** (requires [uv](https://docs.astral.sh/uv/) and Python 3.11+):

   ```sh
   git clone <repo-url> sift && cd sift
   uv sync
   ```

2. **Configure** — edit `config.toml` (feeds, model, interest profile; see
   `config.example.toml`), and put your API key in the keychain (never in the
   config or repo):

   ```sh
   security add-generic-password -s ANTHROPIC_API_KEY -a "$USER" -w
   ```

3. **Run**:

   ```sh
   export ANTHROPIC_API_KEY="$(security find-generic-password -s ANTHROPIC_API_KEY -w)"
   uv run sift run
   open digests/*.html
   ```

## Commands

| Command | What it does |
|---|---|
| `uv run sift run` | Full pipeline: fetch → filter → dedup → one API call → render → record |
| `uv run sift run --dry-run` | Everything except the API call; prints what would be sent |
| `uv run sift add <feed-url>` | Validate a feed URL resolves, then append it to `config.toml` |
| `uv run sift list` | List configured feeds |

Output lands in `digests/YYYY-WW.html` and `digests/YYYY-WW.json`. History
lives in `sift.db` (SQLite); logs in `logs/sift.log`. A dead feed never kills
the run — it's logged and skipped.

## Run weekly via launchd (Sunday 6am)

```sh
cp launchd/com.abhijitbansal.sift.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.abhijitbansal.sift.plist
# test it immediately:
launchctl start com.abhijitbansal.sift
```

The plist reads `ANTHROPIC_API_KEY` from the login keychain at run time
(quickstart step 2) and schedules Sunday 06:00 in the machine's local timezone.

## Tests

```sh
uv run python -m pytest
```

## Cost

One API call per weekly run (model set in `config.toml`, default
`claude-opus-4-8`). Everything else — fetching, dedup, rendering, history —
is local and free.

## License

MIT — see [LICENSE](LICENSE).
