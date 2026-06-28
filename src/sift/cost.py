"""Compute the USD cost of one API call from its token usage.

Prices are USD per 1M tokens (input, output), current as of 2026-06 from the
Anthropic pricing reference. Unknown models fall back to the Opus-4 tier so a
cost is always reported rather than silently zeroed.
"""

from __future__ import annotations

from dataclasses import dataclass

TOKENS_PER_MILLION = 1_000_000

# model id -> (input $/1M, output $/1M)
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
DEFAULT_PRICE = (5.0, 25.0)  # assume Opus-tier when the model is unknown


@dataclass(frozen=True)
class CostBreakdown:
    model: str
    input_tokens: int
    output_tokens: int
    input_usd: float
    output_usd: float
    total_usd: float


def price_for(model: str) -> tuple[float, float]:
    """Return (input, output) $/1M rates for a model, defaulting to Opus tier."""
    return PRICES.get(model, DEFAULT_PRICE)


def usage_cost(model: str, input_tokens: int, output_tokens: int) -> CostBreakdown:
    """Compute the cost of a single call. Tokens must be non-negative."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    in_rate, out_rate = price_for(model)
    input_usd = input_tokens / TOKENS_PER_MILLION * in_rate
    output_usd = output_tokens / TOKENS_PER_MILLION * out_rate
    return CostBreakdown(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_usd=round(input_usd, 6),
        output_usd=round(output_usd, 6),
        total_usd=round(input_usd + output_usd, 6),
    )
