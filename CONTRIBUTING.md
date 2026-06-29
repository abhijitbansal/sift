# Contributing to Sift

Sift is a small, single-reader tool. Contributions are welcome, but the bar is
"does it keep Sift simple and useful for one reader" — not feature breadth.

## Setup

```sh
uv sync
uv run python -m pytest
```

## Ground rules

- **One API call per run.** The whole design is "everything local and free
  except a single weekly Claude call." Don't add per-item API calls.
- **Minimal dependencies.** Prefer the standard library. New runtime deps need a
  clear justification.
- **Tests first.** New behavior needs tests; the suite must stay green and
  coverage at or above 80% (`uv run python -m pytest --cov=sift`).
- **Immutable patterns.** Build new objects; don't mutate inputs in place.
- **Small, focused files.** Organize by feature (`fetch`, `dedup`, `rank`,
  `render`, `site`, `deliver`, `cost`, `filters`, `store`).

## Secrets

Never commit secrets. The Anthropic key and the SMTP password live in the macOS
keychain or env vars only. CI runs without any secrets (network and SMTP are
mocked in tests).

## Pull requests

1. Branch off `main`.
2. Keep the change focused; explain the "why" in the description.
3. Make sure CI is green before requesting review.

`main` is protected: direct pushes are blocked, the `test` CI check must pass,
and a code-owner review is required (see `.github/CODEOWNERS`). The maintainer
self-merges via admin; everyone else's PR needs the maintainer's approval.
