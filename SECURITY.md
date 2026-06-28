# Security

Sift is a personal tool, but it handles two secrets and fetches remote content,
so a few things are worth stating.

## Secrets

- The **Anthropic API key** and the **SMTP password** are never stored in the
  repo or `config.toml`. They are read from the macOS keychain (or the
  `ANTHROPIC_API_KEY` / `SIFT_SMTP_PASSWORD` environment variables) at run time.
- The SMTP password is never logged. If you find any code path that logs or
  persists a secret, treat it as a bug and report it.

## Untrusted input

- Feed content is untrusted. All HTML pulled from feeds is stripped of tags, and
  all rendered output is HTML-escaped before it reaches the digest or the site.
- Feed URLs in `config.toml` are fetched directly; only add feeds you trust.

## Reporting

Found a vulnerability? Open a private security advisory on the repository, or
email the maintainer. Please don't file a public issue for anything that could
expose a secret or be abused before it's fixed.
