"""One Claude API call: merge remaining duplicates, categorize, score, summarize."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sift.config import Config
from sift.fetch import Item

log = logging.getLogger("sift.rank")

CATEGORIES = ("models_research", "tooling", "infra", "policy", "business")
MAX_RESPONSE_TOKENS = 32000


class RankError(RuntimeError):
    """The ranking call returned something unusable (refusal, truncation, no JSON)."""


@dataclass(frozen=True)
class RankResult:
    stories: list[dict]
    model: str
    input_tokens: int
    output_tokens: int


RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "IDs of the input clusters this story merges (>= 1).",
                    },
                    "title": {"type": "string", "description": "Clean canonical headline."},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "score": {
                        "type": "integer",
                        "description": "Importance 1-10 given the reader's interest profile.",
                    },
                    "rationale": {"type": "string", "description": "One line: why this score."},
                    "summary": {"type": "string", "description": "Exactly two neutral sentences."},
                    "needs_verification": {
                        "type": "boolean",
                        "description": "True if the central claim is not from a primary source.",
                    },
                },
                "required": [
                    "cluster_ids",
                    "title",
                    "category",
                    "score",
                    "rationale",
                    "summary",
                    "needs_verification",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stories"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You curate a private weekly AI-news digest for one reader. You receive clustered "
    "news items (already roughly deduplicated by title similarity). Your job: merge any "
    "clusters that still cover the same story, categorize each story, score its importance "
    "1-10 against the reader's interest profile, write a two-sentence neutral summary, and "
    "flag stories whose central claim does not come from a primary source (official blog, "
    "paper, or announcement). Include every input cluster in exactly one output story."
)


def build_payload(clusters: list[list[Item]]) -> list[dict]:
    """Compact JSON-ready view of each cluster for the prompt."""
    return [
        {
            "id": idx,
            "title": cluster[0].title,
            "url": cluster[0].url,
            "sources": sorted({item.source for item in cluster}),
            "summary": cluster[0].summary,
        }
        for idx, cluster in enumerate(clusters)
    ]


def build_prompt(payload: list[dict], config: Config) -> str:
    parts = [
        f"Reader interest profile:\n{config.interest_profile}\n",
        f"Top stories wanted per digest: {config.max_items_per_digest} "
        "(score generously only where deserved; the renderer keeps the top N).\n",
    ]
    if config.mute:
        muted = ", ".join(config.mute)
        parts.append(
            "Down-rank or exclude stories primarily about these muted topics: "
            f"{muted}.\n"
        )
    weighted = [f"{f.name} (x{f.weight:g})" for f in config.feeds if f.weight != 1.0]
    if weighted:
        parts.append(
            "Source weighting hints (higher = more trusted/important to this reader): "
            f"{', '.join(weighted)}.\n"
        )
    if config.boost:
        boosted = ", ".join(config.boost)
        parts.append(
            "Watchlist: strongly prioritize stories about these entities/topics — raise their "
            f"importance score by ~2 points and surface them even when borderline: {boosted}.\n"
        )
    parts.append("News clusters (JSON):\n" + json.dumps(payload, indent=2, sort_keys=True))
    return "\n".join(parts)


def parse_response(response: object, cluster_count: int, model: str) -> RankResult:
    """Validate a Message-like response and extract ranked stories. Pure: no I/O."""
    _check_stop_reason(response)
    text = _first_text(response)
    try:
        stories = json.loads(text)["stories"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RankError(f"Ranking response was not valid stories JSON: {exc}") from exc
    usage = response.usage
    validated = []
    for story in stories:
        entry = _validated(story, cluster_count)
        if entry is None:
            log.warning(
                "Dropping story with no valid cluster_ids (model returned %r): %r",
                story.get("cluster_ids"),
                story.get("title"),
            )
            continue
        validated.append(entry)
    return RankResult(
        stories=validated,
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )


def build_call_kwargs(payload: list[dict], config: Config) -> dict:
    """Assemble the messages.stream kwargs. Thinking is omitted unless adaptive."""
    output_config: dict = {"format": {"type": "json_schema", "schema": RANKING_SCHEMA}}
    if config.effort:
        output_config["effort"] = config.effort
    kwargs: dict = {
        "model": config.model,
        "max_tokens": MAX_RESPONSE_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_prompt(payload, config)}],
        "output_config": output_config,
    }
    if config.thinking == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}
    return kwargs


def rank_clusters(clusters: list[list[Item]], config: Config) -> RankResult:
    """The single API call of the weekly run. Returns validated stories + usage."""
    import anthropic
    import httpx

    payload = build_payload(clusters)
    client = anthropic.Anthropic()
    kwargs = build_call_kwargs(payload, config)
    try:
        with client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()
    except (httpx.RemoteProtocolError, anthropic.APIConnectionError):
        log.warning("Ranking stream dropped mid-response, retrying once")
        with client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()
    log.info(
        "API call done: %s in / %s out tokens, stop_reason=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.stop_reason,
    )
    return parse_response(response, len(clusters), config.model)


def _check_stop_reason(response: object) -> None:
    reason = getattr(response, "stop_reason", None)
    if reason == "refusal":
        raise RankError("Model refused the ranking request (stop_reason=refusal).")
    if reason == "max_tokens":
        raise RankError(
            "Ranking response was truncated (stop_reason=max_tokens); "
            "raise MAX_RESPONSE_TOKENS."
        )


def _first_text(response: object) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise RankError("Ranking response contained no text block.")


def _validated(story: dict, cluster_count: int) -> dict | None:
    """Clamp and sanitize a story; return None if it maps to no valid cluster."""
    cluster_ids = [i for i in story["cluster_ids"] if 0 <= i < cluster_count]
    if not cluster_ids:
        return None
    return {
        **story,
        "cluster_ids": cluster_ids,
        "score": min(10, max(1, int(story["score"]))),
        "category": story["category"] if story["category"] in CATEGORIES else "models_research",
    }
