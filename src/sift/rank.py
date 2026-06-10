"""One Claude API call: merge remaining duplicates, categorize, score, summarize."""

from __future__ import annotations

import json
import logging

from sift.config import Config
from sift.fetch import Item

log = logging.getLogger("sift.rank")

CATEGORIES = ("models_research", "tooling", "infra", "policy", "business")
MAX_RESPONSE_TOKENS = 16000

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
    return (
        f"Reader interest profile:\n{config.interest_profile}\n\n"
        f"Top stories wanted per digest: {config.max_items_per_digest} "
        "(score generously only where deserved; the renderer keeps the top N).\n\n"
        "News clusters (JSON):\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def rank_clusters(clusters: list[list[Item]], config: Config) -> list[dict]:
    """The single API call of the weekly run. Returns validated story dicts."""
    import anthropic

    payload = build_payload(clusters)
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=config.model,
        max_tokens=MAX_RESPONSE_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(payload, config)}],
        output_config={"format": {"type": "json_schema", "schema": RANKING_SCHEMA}},
    )
    log.info(
        "API call done: %s in / %s out tokens, stop_reason=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.stop_reason,
    )
    text = next(block.text for block in response.content if block.type == "text")
    stories = json.loads(text)["stories"]
    return [_validated(story, len(clusters)) for story in stories]


def _validated(story: dict, cluster_count: int) -> dict:
    cluster_ids = [i for i in story["cluster_ids"] if 0 <= i < cluster_count]
    return {
        **story,
        "cluster_ids": cluster_ids or [0],
        "score": min(10, max(1, int(story["score"]))),
        "category": story["category"] if story["category"] in CATEGORIES else "models_research",
    }
