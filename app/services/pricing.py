"""Anthropic API pricing — used to estimate cost of agent runs.

Prices are USD per 1,000,000 tokens for each rate class. Update when
Anthropic changes their public list pricing. The Messages API does not
return cost in the response, only token usage, so we compute it client-side.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPricing:
    """USD per 1,000,000 tokens at each rate class."""

    input_per_m: Decimal
    output_per_m: Decimal
    cache_write_per_m: Decimal
    cache_read_per_m: Decimal


# Source: Anthropic public pricing as of 2026-05. Keep this table in sync
# with https://www.anthropic.com/pricing.
PRICES: dict[str, ModelPricing] = {
    "claude-opus-4-7": ModelPricing(
        input_per_m=Decimal("15.00"),
        output_per_m=Decimal("75.00"),
        cache_write_per_m=Decimal("18.75"),
        cache_read_per_m=Decimal("1.50"),
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_m=Decimal("3.00"),
        output_per_m=Decimal("15.00"),
        cache_write_per_m=Decimal("3.75"),
        cache_read_per_m=Decimal("0.30"),
    ),
    "claude-haiku-4-5": ModelPricing(
        input_per_m=Decimal("0.80"),
        output_per_m=Decimal("4.00"),
        cache_write_per_m=Decimal("1.00"),
        cache_read_per_m=Decimal("0.08"),
    ),
}

# Anthropic charges this per web_search tool invocation on top of token usage.
WEB_SEARCH_PRICE_USD = Decimal("0.01")

_PER_MILLION = Decimal("1000000")
_ROUND_TO = Decimal("0.0001")


def compute_cost(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    web_search_count: int = 0,
) -> Decimal:
    """Return the estimated USD cost for a single agent run.

    Returns 0 (and logs a warning) for unknown models so admin pages never
    crash on a model rename. Update PRICES to add coverage.
    """
    pricing = PRICES.get(model)
    if pricing is None:
        logger.warning(
            "No pricing entry for model %r — cost estimate will be 0. "
            "Add an entry in app/services/pricing.py to fix.",
            model,
        )
        return Decimal("0")

    token_cost = (
        Decimal(input_tokens) * pricing.input_per_m
        + Decimal(output_tokens) * pricing.output_per_m
        + Decimal(cache_creation_tokens) * pricing.cache_write_per_m
        + Decimal(cache_read_tokens) * pricing.cache_read_per_m
    ) / _PER_MILLION

    search_cost = Decimal(web_search_count) * WEB_SEARCH_PRICE_USD
    return (token_cost + search_cost).quantize(_ROUND_TO)
