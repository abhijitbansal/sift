# Roadmap

Where Sift is and where it's going. This page is the living plan — it changes as
the tool does.

## Shipped in v2

- **Robust ranking call** — adaptive thinking, and clear errors on model refusal
  or truncated output instead of a broken digest.
- **Cost tracking** — every run records token counts and USD cost; `sift history`
  shows the running total.
- **Tuning controls** — per-feed `weight`, a `min_score` cutoff, and a `mute`
  list, all driven from `config.toml`.
- **Email delivery** — the weekly digest can be emailed over SMTP, with the
  password kept in the keychain.
- **This site** — an all-in-one explainer, usage guide, roadmap, and a browsable
  archive of every digest, generated from the pipeline itself.
- **Full test coverage** across the pipeline.

## Near-term

- **First real end-to-end run** — pending an `ANTHROPIC_API_KEY` in the keychain;
  once it runs, the first digest gets committed and appears in the archive.
- **GitHub Pages** — publish this site (served from `/docs`) once the repo is
  ready to go public.
- **Go public** — after a working-tree and git-history secret scan passes.

## Ideas / backlog

- A search box over the digest archive.
- Per-category caps (e.g. at most three "business" stories per week).
- A "read it / skip it" feedback signal that nudges future scoring.
- An RSS feed of the digests themselves, for reading in a feed reader.
- Optional push notification (ntfy/Pushover) linking to the latest digest.

## Known limitations

- macOS-first: keychain helpers and the launchd schedule assume macOS. The core
  pipeline is plain Python and runs anywhere with the key in an env var.
- Single reader: the interest profile and digest are built for one person by
  design. Multi-reader support is explicitly out of scope.
- Local dedup is greedy title-similarity; the model catches the rest during
  ranking.
