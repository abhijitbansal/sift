"""Unit tests for title normalization and dedup clustering."""

from sift.dedup import cluster_items, normalize_title, titles_similar
from sift.fetch import Item


def make_item(title: str, source: str = "Test Feed") -> Item:
    return Item(title=title, url=f"https://example.com/{hash(title)}", source=source,
                published=None, summary="")


def test_normalize_title_lowercases_and_strips_punctuation():
    # Arrange
    title = "OpenAI Releases GPT-5!!  (Official)"

    # Act
    normalized = normalize_title(title)

    # Assert
    assert normalized == "openai releases gpt 5 official"


def test_titles_similar_detects_near_duplicates():
    assert titles_similar(
        "Anthropic launches Claude Opus 4.8",
        "Anthropic Launches Claude Opus 4.8!",
    )


def test_titles_similar_rejects_unrelated_titles():
    assert not titles_similar(
        "Anthropic launches Claude Opus 4.8",
        "EU passes new AI safety regulation",
    )


def test_cluster_items_groups_duplicates_from_different_feeds():
    # Arrange
    items = [
        make_item("Anthropic launches Claude Opus 4.8", source="Feed A"),
        make_item("Anthropic Launches Claude Opus 4.8!", source="Feed B"),
        make_item("EU passes new AI safety regulation", source="Feed C"),
    ]

    # Act
    clusters = cluster_items(items)

    # Assert
    assert len(clusters) == 2
    assert len(clusters[0]) == 2
    assert {item.source for item in clusters[0]} == {"Feed A", "Feed B"}
    assert len(clusters[1]) == 1


def test_cluster_items_keeps_distinct_stories_separate():
    items = [
        make_item("Nvidia ships new GPU"),
        make_item("OpenAI raises funding round"),
        make_item("Meta releases open-source model"),
    ]

    clusters = cluster_items(items)

    assert len(clusters) == 3


def test_cluster_items_empty_input_returns_empty():
    assert cluster_items([]) == []
