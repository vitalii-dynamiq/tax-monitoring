"""Tests for app/services/pricing.py."""

from decimal import Decimal

from app.services.pricing import (
    PRICES,
    WEB_SEARCH_PRICE_USD,
    compute_cost,
)


class TestComputeCost:
    def test_zero_usage_is_zero(self):
        assert compute_cost(
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
        ) == Decimal("0")

    def test_input_output_only(self):
        # Sonnet 4.6: $3/1M input, $15/1M output
        # 1M input + 100k output = 3.00 + 1.50 = 4.50
        cost = compute_cost(
            "claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=100_000,
        )
        assert cost == Decimal("4.5000")

    def test_includes_cache_tokens(self):
        # 1M cache writes ($3.75) + 1M cache reads ($0.30) = 4.05
        cost = compute_cost(
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=1_000_000,
            cache_read_tokens=1_000_000,
        )
        assert cost == Decimal("4.0500")

    def test_web_search_adds_per_call_charge(self):
        # 5 searches × $0.01 = $0.05
        cost = compute_cost(
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            web_search_count=5,
        )
        assert cost == Decimal("5") * WEB_SEARCH_PRICE_USD == Decimal("0.05")

    def test_unknown_model_returns_zero(self, caplog):
        cost = compute_cost(
            "claude-not-a-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            web_search_count=10,
        )
        assert cost == Decimal("0")
        assert any("No pricing entry" in r.message for r in caplog.records)

    def test_realistic_run(self):
        # Typical monitoring run: 50k in, 10k out, 7 searches on sonnet
        cost = compute_cost(
            "claude-sonnet-4-6",
            input_tokens=50_000,
            output_tokens=10_000,
            web_search_count=7,
        )
        # input: 50_000 * 3 / 1_000_000 = 0.15
        # output: 10_000 * 15 / 1_000_000 = 0.15
        # web: 7 * 0.01 = 0.07
        # total: 0.37
        assert cost == Decimal("0.3700")

    def test_all_three_models_priced(self):
        # Sanity: every model we ship has a pricing entry.
        for model in ("claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"):
            assert model in PRICES
