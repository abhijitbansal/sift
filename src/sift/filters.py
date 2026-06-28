"""Mechanical post-rank filters: per-source weighting and a minimum-score cutoff.

These run after the model has scored stories. Source weighting reflects how much
the reader trusts each feed; the min-score cutoff drops weak stories even when the
digest has not yet hit its item cap. (Muting is semantic and handled in the prompt.)
"""

from __future__ import annotations

from sift.config import Config
from sift.fetch import Item


def apply_source_weight(
    stories: list[dict], clusters: list[list[Item]], config: Config
) -> list[dict]:
    """Multiply each story's score by the largest weight among its source feeds.

    Result is re-clamped to 1..10 and rounded to an int, preserving the schema.
    """
    weight_by_name = {feed.name: feed.weight for feed in config.feeds}
    weighted = []
    for story in stories:
        sources = {
            item.source
            for cid in story["cluster_ids"]
            for item in clusters[cid]
        }
        factor = max((weight_by_name.get(src, 1.0) for src in sources), default=1.0)
        score = min(10, max(1, round(story["score"] * factor)))
        weighted.append({**story, "score": score})
    return weighted


def apply_min_score(stories: list[dict], min_score: int) -> list[dict]:
    """Drop stories scoring below the configured threshold."""
    return [story for story in stories if story["score"] >= min_score]
