"""Command-line interface: sift run | add | list | email | history."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sift import config as config_mod
from sift import dedup, fetch, render, store

log = logging.getLogger("sift")

MAX_ITEM_AGE_DAYS = 8


def week_id(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def digests_dir(root: Path) -> Path:
    """Where digests live — under docs/ so they are served by the site."""
    return root / "docs" / "digests"


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "sift.log", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def gather_clusters(cfg: config_mod.Config, db_path: Path) -> list[list[fetch.Item]]:
    """Fetch, drop seen/stale items, cluster. Shared by run and dry-run."""
    items = fetch.fetch_all(cfg.feeds)
    log.info("Fetched %d items total", len(items))

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ITEM_AGE_DAYS)
    with store.connect(db_path) as conn:
        seen = store.seen_urls(conn)
    fresh = [
        item
        for item in items
        if item.url not in seen and (item.published is None or item.published >= cutoff)
    ]
    log.info("%d items survive seen/age filters", len(fresh))

    clusters = dedup.cluster_items(fresh)
    log.info("%d clusters after local dedup", len(clusters))
    return clusters


def cmd_run(args: argparse.Namespace) -> int:
    from sift import cost, deliver, filters, rank

    cfg = config_mod.load_config(args.config)
    root = args.config.parent
    db_path = root / "sift.db"
    clusters = gather_clusters(cfg, db_path)
    if not clusters:
        log.info("Nothing new this week; no digest written.")
        return 0

    if args.dry_run:
        payload = rank.build_payload(clusters)
        print(rank.SYSTEM_PROMPT, "\n")
        print(rank.build_prompt(payload, cfg))
        print(f"\n[dry-run] Would send {len(payload)} clusters to {cfg.model}.")
        return 0

    result = rank.rank_clusters(clusters, cfg)
    stories = filters.apply_source_weight(result.stories, clusters, cfg)
    stories = filters.apply_min_score(stories, cfg.min_score)

    week = week_id(datetime.now(timezone.utc))
    digest = render.build_digest(week, stories, clusters)
    digest["stories"] = digest["stories"][: cfg.max_items_per_digest]

    out_dir = digests_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{week}.html"
    render.render_html(digest, html_path)
    render.render_json(digest, out_dir / f"{week}.json")

    breakdown = cost.usage_cost(result.model, result.input_tokens, result.output_tokens)
    log.info(
        "Wrote docs/digests/%s.html and .json (%d stories); run cost $%.4f",
        week,
        len(digest["stories"]),
        breakdown.total_usd,
    )

    with store.connect(db_path) as conn:
        store.record_items(conn, [item for cluster in clusters for item in cluster], week)
        store.record_digest(
            conn,
            week,
            len(digest["stories"]),
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=breakdown.total_usd,
        )

    _maybe_rebuild_site(root, db_path)

    if cfg.email and cfg.email.enabled:
        try:
            deliver.send_digest(cfg.email, html_path.read_text(encoding="utf-8"), week)
        except deliver.DeliveryError as exc:
            log.error("Digest written but email delivery failed: %s", exc)
    return 0


def cmd_email(args: argparse.Namespace) -> int:
    from sift import deliver

    cfg = config_mod.load_config(args.config)
    if not (cfg.email and cfg.email.enabled):
        print(
            "Email delivery is not enabled. Set [email] enabled = true in config.toml.",
            file=sys.stderr,
        )
        return 1
    html_path = digests_dir(args.config.parent) / f"{args.week}.html"
    if not html_path.exists():
        print(f"No digest found at {html_path}", file=sys.stderr)
        return 1
    try:
        deliver.send_digest(cfg.email, html_path.read_text(encoding="utf-8"), args.week)
    except deliver.DeliveryError as exc:
        print(f"Email failed: {exc}", file=sys.stderr)
        return 1
    print(f"Emailed digest {args.week} to {cfg.email.recipient}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    db_path = args.config.parent / "sift.db"
    with store.connect(db_path) as conn:
        records = store.digest_history(conn)
    if not records:
        print("No digests recorded yet.")
        return 0
    for record in records:
        print(
            f"{record.week}  {record.item_count:2d} stories  "
            f"{(record.model or '-'):18s}  "
            f"{record.input_tokens:>7d} in / {record.output_tokens:>6d} out  "
            f"${record.cost_usd:.4f}"
        )
    total = sum(record.cost_usd for record in records)
    print(f"\nTotal across {len(records)} runs: ${total:.4f}")
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    from sift import site

    root = args.config.parent
    db_path = root / "sift.db"
    cfg = config_mod.load_config(args.config)
    pages = site.build_site(root, db_path, cfg)
    print(f"Built {pages} site page(s) under docs/.")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    import feedparser
    import httpx

    try:
        response = httpx.get(
            args.url,
            timeout=fetch.FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": fetch.USER_AGENT},
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"Feed did not resolve: {exc}", file=sys.stderr)
        return 1
    parsed = feedparser.parse(response.content)
    if not parsed.entries:
        print("URL resolved but contains no feed entries; not adding.", file=sys.stderr)
        return 1
    name = (parsed.feed.get("title") or args.url).strip()
    config_mod.append_feed(args.config, name, args.url)
    print(f"Added feed: {name} ({args.url})")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = config_mod.load_config(args.config)
    for feed in cfg.feeds:
        hint = f"  [{feed.category_hint}]" if feed.category_hint else ""
        weight = f"  (x{feed.weight:g})" if feed.weight != 1.0 else ""
        print(f"{feed.name}: {feed.url}{hint}{weight}")
    return 0


def _maybe_rebuild_site(root: Path, db_path: Path) -> None:
    """Rebuild the static site after a run; never let it fail the run."""
    try:
        from sift import site

        cfg = config_mod.load_config(root / "config.toml")
        site.build_site(root, db_path, cfg)
    except Exception:  # noqa: BLE001 - site rebuild is best-effort
        log.exception("Site rebuild failed (digest still written)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sift", description="Weekly AI-news digest pipeline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "config.toml",
        help="Path to config.toml (default: project root)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run the weekly pipeline")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be sent to the API; no API call"
    )
    run_parser.set_defaults(func=cmd_run)

    add_parser = sub.add_parser("add", help="Add a feed URL to config.toml")
    add_parser.add_argument("url")
    add_parser.set_defaults(func=cmd_add)

    list_parser = sub.add_parser("list", help="List configured feeds")
    list_parser.set_defaults(func=cmd_list)

    email_parser = sub.add_parser("email", help="Email a previously rendered digest")
    email_parser.add_argument("week", help="Digest week id, e.g. 2026-26")
    email_parser.set_defaults(func=cmd_email)

    history_parser = sub.add_parser("history", help="Show run history and cost")
    history_parser.set_defaults(func=cmd_history)

    site_parser = sub.add_parser("site", help="Rebuild the static site under docs/")
    site_parser.set_defaults(func=cmd_site)

    args = parser.parse_args(argv)
    setup_logging(args.config.parent / "logs")
    try:
        return args.func(args)
    except Exception:
        log.exception("sift %s failed", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
