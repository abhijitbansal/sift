"""Load and validate config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_ITEMS = 10


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    category_hint: str | None = None


@dataclass(frozen=True)
class Config:
    feeds: tuple[Feed, ...]
    model: str
    max_items_per_digest: int
    interest_profile: str


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    feeds_raw = raw.get("feeds", [])
    if not feeds_raw:
        raise ValueError("config.toml must define at least one [[feeds]] entry")
    feeds = []
    for entry in feeds_raw:
        if "name" not in entry or "url" not in entry:
            raise ValueError(f"Feed entry missing 'name' or 'url': {entry}")
        feeds.append(Feed(entry["name"], entry["url"], entry.get("category_hint")))

    sift_cfg = raw.get("sift", {})
    profile = str(sift_cfg.get("interest_profile", "")).strip()
    if not profile:
        raise ValueError("config.toml must set sift.interest_profile")

    max_items = int(sift_cfg.get("max_items_per_digest", DEFAULT_MAX_ITEMS))
    if max_items < 1:
        raise ValueError("sift.max_items_per_digest must be >= 1")

    return Config(
        feeds=tuple(feeds),
        model=str(sift_cfg.get("model", DEFAULT_MODEL)),
        max_items_per_digest=max_items,
        interest_profile=profile,
    )


def append_feed(path: Path, name: str, url: str) -> None:
    """Append a [[feeds]] entry to config.toml (tomllib is read-only)."""
    name = name.replace('"', "'")
    block = f'\n[[feeds]]\nname = "{name}"\nurl = "{url}"\n'
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
