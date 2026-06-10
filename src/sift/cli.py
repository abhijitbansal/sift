"""Command-line interface: sift run [--dry-run] | sift add <url> | sift list."""

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
    from sift import rank  # deferred so dry-run works without the anthropic client set up

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

    stories = rank.rank_clusters(clusters, cfg)
    week = week_id(datetime.now(timezone.utc))
    digest = render.build_digest(week, stories, clusters)
    digest["stories"] = digest["stories"][: cfg.max_items_per_digest]

    digests_dir = root / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    render.render_html(digest, digests_dir / f"{week}.html")
    render.render_json(digest, digests_dir / f"{week}.json")
    log.info("Wrote digests/%s.html and .json (%d stories)", week, len(digest["stories"]))

    with store.connect(db_path) as conn:
        store.record_items(conn, [item for cluster in clusters for item in cluster], week)
        store.record_digest(conn, week, len(digest["stories"]))
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
        print(f"{feed.name}: {feed.url}{hint}")
    return 0


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

    args = parser.parse_args(argv)
    setup_logging(args.config.parent / "logs")
    try:
        return args.func(args)
    except Exception:
        log.exception("sift %s failed", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
