"""Unit tests for ranking response parsing, validation, and prompt assembly.

The network call (rank_clusters) is not unit-tested — it needs a live key.
parse_response and the prompt builders hold all the logic worth testing.
"""

import json
from types import SimpleNamespace

import pytest

from sift.config import Config, Feed
from sift.rank import (
    RankError,
    build_payload,
    build_prompt,
    parse_response,
)
from sift.fetch import Item


def make_config(**overrides) -> Config:
    base = dict(
        feeds=(Feed("Feed A", "https://a", None, 1.0),),
        model="claude-opus-4-8",
        max_items_per_digest=10,
        interest_profile="I care about agentic dev tooling and model releases.",
    )
    base.update(overrides)
    return Config(**base)


def fake_response(stories, stop_reason="end_turn", in_tokens=1000, out_tokens=500):
    text = json.dumps({"stories": stories})
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        usage=SimpleNamespace(input_tokens=in_tokens, output_tokens=out_tokens),
    )


def valid_story(**overrides):
    base = dict(
        cluster_ids=[0],
        title="A thing happened",
        category="tooling",
        score=7,
        rationale="Relevant to dev tooling.",
        summary="One sentence. Two sentence.",
        needs_verification=False,
    )
    base.update(overrides)
    return base


def test_parse_response_extracts_and_validates_stories():
    response = fake_response([valid_story()])

    result = parse_response(response, cluster_count=1, model="claude-opus-4-8")

    assert len(result.stories) == 1
    assert result.stories[0]["title"] == "A thing happened"
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.model == "claude-opus-4-8"


def test_parse_response_clamps_out_of_range_score():
    response = fake_response([valid_story(score=99)])

    result = parse_response(response, cluster_count=1, model="m")

    assert result.stories[0]["score"] == 10


def test_parse_response_drops_invalid_cluster_ids():
    response = fake_response([valid_story(cluster_ids=[5, 0])])

    result = parse_response(response, cluster_count=1, model="m")

    assert result.stories[0]["cluster_ids"] == [0]


def test_parse_response_drops_story_with_all_invalid_cluster_ids():
    # All ids out of range -> story is unmappable -> dropped, not misattributed to cluster 0.
    response = fake_response([valid_story(cluster_ids=[7, 8]), valid_story(title="ok")])

    result = parse_response(response, cluster_count=1, model="m")

    assert [s["title"] for s in result.stories] == ["ok"]


def test_parse_response_falls_back_unknown_category():
    response = fake_response([valid_story(category="not_a_category")])

    result = parse_response(response, cluster_count=1, model="m")

    assert result.stories[0]["category"] == "models_research"


def test_parse_response_raises_on_refusal():
    response = fake_response([], stop_reason="refusal")

    with pytest.raises(RankError, match="refused"):
        parse_response(response, cluster_count=1, model="m")


def test_parse_response_raises_on_truncation():
    response = fake_response([valid_story()], stop_reason="max_tokens")

    with pytest.raises(RankError, match="truncated"):
        parse_response(response, cluster_count=1, model="m")


def test_parse_response_raises_when_no_text_block():
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking", thinking="")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )

    with pytest.raises(RankError, match="no text block"):
        parse_response(response, cluster_count=1, model="m")


def test_build_payload_collapses_cluster_sources():
    clusters = [[
        Item("Title", "https://x", "Feed A", None, "summary"),
        Item("Title dup", "https://y", "Feed B", None, "other"),
    ]]

    payload = build_payload(clusters)

    assert payload[0]["id"] == 0
    assert payload[0]["sources"] == ["Feed A", "Feed B"]


def test_build_prompt_includes_mute_topics():
    cfg = make_config(mute=("chatbot drama", "ai doom"))

    prompt = build_prompt([], cfg)

    assert "chatbot drama" in prompt
    assert "ai doom" in prompt


def test_build_prompt_includes_nondefault_source_weights():
    cfg = make_config(
        feeds=(Feed("Trusted", "https://t", None, 2.0), Feed("Normal", "https://n", None, 1.0)),
    )

    prompt = build_prompt([], cfg)

    assert "Trusted (x2)" in prompt
    assert "Normal" not in prompt  # weight 1.0 is the default; not surfaced
