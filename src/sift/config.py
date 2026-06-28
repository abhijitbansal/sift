"""Load and validate config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_ITEMS = 10
DEFAULT_MIN_SCORE = 1
DEFAULT_SMTP_PORT = 587
DEFAULT_THINKING = "off"
THINKING_MODES = ("off", "adaptive")
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    category_hint: str | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool
    host: str
    sender: str
    recipient: str
    port: int = DEFAULT_SMTP_PORT
    use_tls: bool = True


@dataclass(frozen=True)
class Config:
    feeds: tuple[Feed, ...]
    model: str
    max_items_per_digest: int
    interest_profile: str
    mute: tuple[str, ...] = ()
    min_score: int = DEFAULT_MIN_SCORE
    thinking: str = DEFAULT_THINKING
    effort: str | None = None
    email: EmailConfig | None = None


def _parse_feeds(feeds_raw: list[dict]) -> tuple[Feed, ...]:
    if not feeds_raw:
        raise ValueError("config.toml must define at least one [[feeds]] entry")
    feeds = []
    for entry in feeds_raw:
        if "name" not in entry or "url" not in entry:
            raise ValueError(f"Feed entry missing 'name' or 'url': {entry}")
        weight = float(entry.get("weight", 1.0))
        if weight <= 0:
            raise ValueError(f"Feed '{entry['name']}' weight must be > 0, got {weight}")
        feeds.append(Feed(entry["name"], entry["url"], entry.get("category_hint"), weight))
    return tuple(feeds)


def _parse_email(raw: dict | None) -> EmailConfig | None:
    if not raw:
        return None
    enabled = bool(raw.get("enabled", False))
    if not enabled:
        return EmailConfig(enabled=False, host="", sender="", recipient="")
    for required in ("host", "from", "to"):
        if not raw.get(required):
            raise ValueError(f"[email] is enabled but missing '{required}'")
    return EmailConfig(
        enabled=True,
        host=str(raw["host"]),
        sender=str(raw["from"]),
        recipient=str(raw["to"]),
        port=int(raw.get("port", DEFAULT_SMTP_PORT)),
        use_tls=bool(raw.get("use_tls", True)),
    )


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    feeds = _parse_feeds(raw.get("feeds", []))

    sift_cfg = raw.get("sift", {})
    profile = str(sift_cfg.get("interest_profile", "")).strip()
    if not profile:
        raise ValueError("config.toml must set sift.interest_profile")

    max_items = int(sift_cfg.get("max_items_per_digest", DEFAULT_MAX_ITEMS))
    if max_items < 1:
        raise ValueError("sift.max_items_per_digest must be >= 1")

    min_score = int(sift_cfg.get("min_score", DEFAULT_MIN_SCORE))
    if not 1 <= min_score <= 10:
        raise ValueError("sift.min_score must be between 1 and 10")

    mute = tuple(str(topic).strip() for topic in sift_cfg.get("mute", []) if str(topic).strip())

    thinking = str(sift_cfg.get("thinking", DEFAULT_THINKING)).lower()
    if thinking not in THINKING_MODES:
        raise ValueError(f"sift.thinking must be one of {THINKING_MODES}")

    effort = sift_cfg.get("effort")
    if effort is not None:
        effort = str(effort).lower()
        if effort not in EFFORT_LEVELS:
            raise ValueError(f"sift.effort must be one of {EFFORT_LEVELS}")

    return Config(
        feeds=feeds,
        model=str(sift_cfg.get("model", DEFAULT_MODEL)),
        max_items_per_digest=max_items,
        interest_profile=profile,
        mute=mute,
        min_score=min_score,
        thinking=thinking,
        effort=effort,
        email=_parse_email(raw.get("email")),
    )


def append_feed(path: Path, name: str, url: str) -> None:
    """Append a [[feeds]] entry to config.toml (tomllib is read-only)."""
    name = name.replace('"', "'")
    block = f'\n[[feeds]]\nname = "{name}"\nurl = "{url}"\n'
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
