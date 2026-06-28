"""Unit tests for token-usage cost computation."""

import pytest

from sift.cost import DEFAULT_PRICE, price_for, usage_cost


def test_usage_cost_computes_known_model_rate():
    # Arrange: Opus 4.8 is $5/1M input, $25/1M output.
    # Act
    breakdown = usage_cost("claude-opus-4-8", input_tokens=1_000_000, output_tokens=1_000_000)

    # Assert
    assert breakdown.input_usd == 5.0
    assert breakdown.output_usd == 25.0
    assert breakdown.total_usd == 30.0


def test_usage_cost_scales_with_token_count():
    breakdown = usage_cost("claude-opus-4-8", input_tokens=200_000, output_tokens=8_000)

    assert breakdown.input_usd == pytest.approx(1.0)
    assert breakdown.output_usd == pytest.approx(0.2)
    assert breakdown.total_usd == pytest.approx(1.2)


def test_usage_cost_unknown_model_falls_back_to_default_tier():
    breakdown = usage_cost("some-future-model", input_tokens=1_000_000, output_tokens=0)

    assert price_for("some-future-model") == DEFAULT_PRICE
    assert breakdown.input_usd == DEFAULT_PRICE[0]


def test_usage_cost_zero_tokens_is_zero_cost():
    breakdown = usage_cost("claude-opus-4-8", input_tokens=0, output_tokens=0)

    assert breakdown.total_usd == 0.0


def test_usage_cost_rejects_negative_tokens():
    with pytest.raises(ValueError):
        usage_cost("claude-opus-4-8", input_tokens=-1, output_tokens=0)
