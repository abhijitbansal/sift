"""Unit tests for mechanical post-rank filters."""

from sift.config import Config, Feed
from sift.fetch import Item
from sift.filters import apply_min_score, apply_source_weight


def make_config(feeds):
    return Config(
        feeds=tuple(feeds),
        model="m",
        max_items_per_digest=10,
        interest_profile="x",
    )


def story(score, cluster_ids):
    return {"score": score, "cluster_ids": cluster_ids, "title": "t"}


def test_apply_source_weight_boosts_trusted_source():
    # Arrange: cluster 0 is from a 2x-weighted feed.
    clusters = [[Item("t", "https://a", "Trusted", None, "")]]
    config = make_config([Feed("Trusted", "https://a", None, 2.0)])

    # Act
    out = apply_source_weight([story(4, [0])], clusters, config)

    # Assert: 4 * 2.0 = 8
    assert out[0]["score"] == 8


def test_apply_source_weight_clamps_to_ten():
    clusters = [[Item("t", "https://a", "Trusted", None, "")]]
    config = make_config([Feed("Trusted", "https://a", None, 3.0)])

    out = apply_source_weight([story(7, [0])], clusters, config)

    assert out[0]["score"] == 10


def test_apply_source_weight_uses_max_weight_across_sources():
    clusters = [[
        Item("t", "https://a", "Trusted", None, ""),
        Item("t", "https://b", "Normal", None, ""),
    ]]
    config = make_config([
        Feed("Trusted", "https://a", None, 2.0),
        Feed("Normal", "https://b", None, 1.0),
    ])

    out = apply_source_weight([story(3, [0])], clusters, config)

    assert out[0]["score"] == 6  # max(2.0, 1.0) applied


def test_apply_source_weight_default_for_unweighted():
    clusters = [[Item("t", "https://a", "Normal", None, "")]]
    config = make_config([Feed("Normal", "https://a", None, 1.0)])

    out = apply_source_weight([story(5, [0])], clusters, config)

    assert out[0]["score"] == 5


def test_apply_min_score_drops_weak_stories():
    stories = [story(2, [0]), story(6, [0]), story(4, [0])]

    kept = apply_min_score(stories, min_score=4)

    assert [s["score"] for s in kept] == [6, 4]


def test_apply_min_score_keeps_all_when_threshold_one():
    stories = [story(1, [0]), story(3, [0])]

    kept = apply_min_score(stories, min_score=1)

    assert len(kept) == 2
