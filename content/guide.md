# Usage guide

Everything you need to install, configure, run, and schedule Sift.

## 1. Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```sh
git clone <repo-url> sift && cd sift
uv sync
```

## 2. Add your Anthropic API key

The key never goes in the config or the repo — it lives in the macOS keychain and
is exported into the environment at run time.

```sh
# store it once
security add-generic-password -s ANTHROPIC_API_KEY -a "$USER" -w

# export it for a run
export ANTHROPIC_API_KEY="$(security find-generic-password -s ANTHROPIC_API_KEY -w)"
```

## 3. Configure `config.toml`

Copy `config.example.toml` to `config.toml` and edit it. The important pieces:

### Interest profile and model

```toml
[sift]
model = "claude-opus-4-8"
max_items_per_digest = 10
min_score = 4          # drop anything the model scores below this
mute = ["chatbot drama", "ai doom punditry"]
boost = ["Ford"]       # watchlist: up-weight these so they surface more reliably
interest_profile = """
I care about enterprise AI adoption, agentic dev tooling, major model
releases, and AI infrastructure. I prefer primary sources and concrete
numbers over hype.
"""
```

| Key | Meaning |
|---|---|
| `model` | Any current Anthropic model id (default `claude-opus-4-8`). |
| `max_items_per_digest` | How many top-scored stories the digest keeps. |
| `min_score` | 1–10 cutoff; stories below it are dropped before the cap. |
| `mute` | Topics the model should down-rank or exclude. |
| `boost` | Watchlist of entities/topics to up-weight so they surface more reliably (e.g. `["Ford"]`). |
| `interest_profile` | Plain-language description of your signal vs. noise. |

### Feeds and weights

```toml
[[feeds]]
name = "Anthropic News"
url = "https://example.com/feed.xml"
category_hint = "models_research"   # optional
weight = 2.0                         # optional, default 1.0
```

`weight` multiplies a story's score when it comes from that feed (and is passed to
the model as a trust hint). Use it to float sources you trust above the rest.

Add a feed without hand-editing by validating it first:

```sh
uv run sift add https://some-blog.example.com/feed.xml
```

### Follow X (Twitter) handles (optional)

X has no open RSS, so Sift reads it through a **bridge** that turns a handle into
a feed. Point `bridge_url` at a bridge (with a `{handle}` placeholder), then add
handles with `sift add-x`:

```toml
[x]
# nitter.net works today, but public Nitter instances are unstable. For
# reliability, self-host Nitter/RSSHub or use an RSS.app feed URL.
bridge_url = "https://nitter.net/{handle}/rss"
```

```sh
uv run sift add-x karpathy      # adds "X · @karpathy" as a feed
uv run sift add-x @DrJimFan     # the @ is optional
```

Each handle is validated against the bridge before it's added, and then behaves
like any other feed. X feeds carry replies and reposts, so if one gets noisy,
down-weight it in `config.toml` (`weight = 0.5`) or remove it. If the bridge
stops resolving, swap `bridge_url` for a self-hosted instance or an RSS.app feed.

### Email delivery (optional)

```toml
[email]
enabled = true
host = "smtp.fastmail.com"
from = "sift@you.example.com"
to = "you@example.com"
port = 587          # 465 uses implicit TLS, anything else uses STARTTLS
use_tls = true
```

The SMTP password is **not** stored here. Put it in the keychain (or the
`SIFT_SMTP_PASSWORD` env var):

```sh
security add-generic-password -s SIFT_SMTP_PASSWORD -a "$USER" -w
```

## 4. Run

```sh
uv run sift run            # full pipeline → digest, history, email, site
uv run sift run --dry-run  # everything except the API call; prints the prompt
```

Output lands in `docs/digests/YYYY-WW.html` and `.json`. History lives in
`sift.db`; logs in `logs/sift.log`.

## 5. Commands

| Command | What it does |
|---|---|
| `sift run` | Full pipeline: fetch → filter → dedup → one API call → render → record → email → site. |
| `sift run --dry-run` | Everything except the API call. |
| `sift add <url>` | Validate a feed URL, then append it to `config.toml`. |
| `sift list` | List configured feeds (with weights). |
| `sift email <week>` | Re-send a rendered digest, e.g. `sift email 2026-26`. |
| `sift history` | Print every run with token counts and cost, plus the running total. |
| `sift site` | Rebuild the static site under `docs/`. |

## 6. Schedule it (Sunday 6am, macOS launchd)

```sh
cp launchd/com.abhijitbansal.sift.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.abhijitbansal.sift.plist
launchctl start com.abhijitbansal.sift   # test it immediately
```

The plist reads `ANTHROPIC_API_KEY` from the login keychain at run time.

## Troubleshooting

- **`Config not found`** — run from the repo root, or pass `--config path/to/config.toml`.
- **`Model refused…` / `truncated`** — Sift raises a clear error instead of
  writing a broken digest; re-run, and if it persists, check the prompt with
  `--dry-run`.
- **Email failed** — the digest is still written; the error names the cause
  (missing `SIFT_SMTP_PASSWORD`, auth, or SMTP). Re-send with `sift email <week>`.
- **A feed stopped working** — it's logged and skipped, never fatal. Check
  `logs/sift.log` and update the URL.
