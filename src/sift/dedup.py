"""Cheap local dedup: cluster near-duplicate items by normalized-title similarity."""

from __future__ import annotations

import difflib
import re

from sift.fetch import Item

TITLE_SIMILARITY_THRESHOLD = 0.85

_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", title.lower())).strip()


def titles_similar(a: str, b: str, threshold: float = TITLE_SIMILARITY_THRESHOLD) -> bool:
    ratio = difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()
    return ratio >= threshold


def cluster_items(items: list[Item]) -> list[list[Item]]:
    """Greedy clustering: each item joins the first cluster whose representative
    (first) item has a similar title; otherwise it starts a new cluster."""
    clusters: list[list[Item]] = []
    for item in items:
        for cluster in clusters:
            if titles_similar(item.title, cluster[0].title):
                cluster.append(item)
                break
        else:
            clusters.append([item])
    return clusters
