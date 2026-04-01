"""
Unit tests for the tax monitoring system.

Tests schema validation, prompt building, change detection logic,
and cron scheduling without requiring a database or AI API.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.services.change_detection_service import _convert_rate_value
from app.services.monitoring_job_service import _compute_next_run, validate_cron_expression
from app.services.prompts.output_schema import (
    AIExtractedRate,
    AIExtractedRule,
    AIMonitoringResult,
)

# ─── Output Schema Validation ───────────────────────────────────────


class TestAIExtractedRate:
    def test_valid_percentage_rate(self):
        rate = AIExtractedRate(
            change_type="new",
            tax_category_code="occ_pct",
            rate_type="percentage",
            rate_value=5.875,
            effective_start="2025-01-01",
            source_quote="The hotel occupancy tax rate is 5.875%.",
            confidence=0.95,
        )
        assert rate.rate_value == 5.875
        assert rate.change_type == "new"

    def test_valid_flat_rate(self):
        rate = AIExtractedRate(
            change_type="unchanged",
            tax_category_code="city_tax_flat",
            rate_type="flat",
            rate_value=3.50,
            currency_code="EUR",
            base_type="per_person_per_night",
            effective_start="2024-01-01",
            source_quote="City tax is EUR 3.50 per person per night.",
            confidence=0.85,
        )
        assert rate.currency_code == "EUR"
        assert rate.base_type == "per_person_per_night"

    def test_valid_tiered_rate(self):
        rate = AIExtractedRate(
            change_type="changed",
            rate_type="tiered",
            tiers=[
                {"min": 0, "max": 100, "rate_value": 2.0},
                {"min": 100, "max": None, "rate_value": 3.5},
            ],
            tier_type="threshold",
            effective_start="2025-06-01",
            source_quote="Rates vary by room price bracket.",
            confidence=0.7,
        )
        assert len(rate.tiers) == 2

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRate(
                change_type="new",
                rate_type="percentage",
                rate_value=5.0,
                effective_start="2025-01-01",
                source_quote="Test",
                confidence=-0.1,
            )

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRate(
                change_type="new",
                rate_type="percentage",
                rate_value=5.0,
                effective_start="2025-01-01",
                source_quote="Test",
                confidence=1.5,
            )

    def test_invalid_change_type_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRate(
                change_type="invalid",
                rate_type="percentage",
                rate_value=5.0,
                effective_start="2025-01-01",
                source_quote="Test",
                confidence=0.5,
            )

    def test_invalid_rate_type_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRate(
                change_type="new",
                rate_type="unknown",
                rate_value=5.0,
                effective_start="2025-01-01",
                source_quote="Test",
                confidence=0.5,
            )

    def test_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRate(
                change_type="new",
                rate_type="percentage",
                # Missing: effective_start, source_quote, confidence
            )


class TestAIExtractedRule:
    def test_valid_exemption_rule(self):
        rule = AIExtractedRule(
            change_type="unchanged",
            rule_type="exemption",
            name="Permanent Resident Exemption",
            description="Stays of 180+ consecutive days are exempt from hotel occupancy tax.",
            conditions={"field": "stay_length_days", "operator": ">=", "value": 180},
            action={"type": "exempt"},
            effective_start="2020-01-01",
            legal_reference="NYC Admin Code §11-2502(a)",
            source_quote="Permanent residents staying 180 days or more are exempt.",
            confidence=0.9,
        )
        assert rule.name == "Permanent Resident Exemption"
        assert rule.conditions["value"] == 180

    def test_valid_reduction_rule(self):
        rule = AIExtractedRule(
            change_type="new",
            rule_type="reduction",
            name="Senior Citizen Discount",
            conditions={"field": "guest_age", "operator": ">=", "value": 65},
            action={"type": "reduce", "reduction_pct": 50},
            effective_start="2025-01-01",
            source_quote="Seniors get 50% reduction.",
            confidence=0.6,
        )
        assert rule.action["reduction_pct"] == 50

    def test_invalid_rule_type_rejected(self):
        with pytest.raises(ValidationError):
            AIExtractedRule(
                change_type="new",
                rule_type="invalid_type",
                name="Test",
                effective_start="2025-01-01",
                source_quote="Test",
                confidence=0.5,
            )


class TestAIMonitoringResult:
    def test_valid_complete_result(self):
        result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Found 3 active tax rates and 2 exemptions. No changes detected.",
            rates=[
                AIExtractedRate(
                    change_type="unchanged",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=5.875,
                    effective_start="2020-01-01",
                    source_quote="NYC hotel occupancy tax is 5.875%.",
                    confidence=0.95,
                ),
            ],
            rules=[
                AIExtractedRule(
                    change_type="unchanged",
                    rule_type="exemption",
                    name="Permanent Resident Exemption",
                    effective_start="2020-01-01",
                    source_quote="180+ day stays exempt.",
                    confidence=0.9,
                ),
            ],
            sources_checked=["https://www.nyc.gov/taxes"],
            overall_confidence=0.9,
        )
        assert result.jurisdiction_code == "US-NY-NYC"
        assert len(result.rates) == 1
        assert len(result.rules) == 1

    def test_empty_result_valid(self):
        result = AIMonitoringResult(
            jurisdiction_code="XX-TEST",
            summary="No tax information found.",
            overall_confidence=0.2,
        )
        assert result.rates == []
        assert result.rules == []

    def test_schema_generates_valid_json(self):
        schema = AIMonitoringResult.model_json_schema()
        assert "properties" in schema
        assert "jurisdiction_code" in schema["properties"]
        assert "rates" in schema["properties"]
        assert "rules" in schema["properties"]


# ─── Prompt Building ────────────────────────────────────────────────


class TestPromptBuilding:
    def test_build_user_prompt_with_urls(self):
        from unittest.mock import MagicMock

        from app.services.prompts.tax_monitoring import build_user_prompt

        jurisdiction = MagicMock()
        jurisdiction.code = "US-NY-NYC"
        jurisdiction.name = "New York City"
        jurisdiction.jurisdiction_type = "city"
        jurisdiction.country_code = "US"
        jurisdiction.currency_code = "USD"
        jurisdiction.path = "US.NY.NYC"
        jurisdiction.local_name = None

        urls = ["https://www.nyc.gov/taxes", "https://tax.ny.gov"]
        prompt = build_user_prompt(jurisdiction, [], [], urls)

        assert "US-NY-NYC" in prompt
        assert "New York City" in prompt
        assert "https://www.nyc.gov/taxes" in prompt
        assert "https://tax.ny.gov" in prompt
        assert "Priority Government Domains" in prompt

    def test_build_user_prompt_without_urls(self):
        from unittest.mock import MagicMock

        from app.services.prompts.tax_monitoring import build_user_prompt

        jurisdiction = MagicMock()
        jurisdiction.code = "XX-TEST"
        jurisdiction.name = "Test"
        jurisdiction.jurisdiction_type = "city"
        jurisdiction.country_code = "XX"
        jurisdiction.currency_code = "XXX"
        jurisdiction.path = "XX"
        jurisdiction.local_name = None

        prompt = build_user_prompt(jurisdiction, [], [], [])
        assert "No specific domains configured" in prompt

    def test_system_prompt_mentions_web_search(self):
        from app.services.prompts.tax_monitoring import SYSTEM_PROMPT

        assert "web search" in SYSTEM_PROMPT.lower()
        assert "report_tax_findings" in SYSTEM_PROMPT


# ─── Cron Scheduling ────────────────────────────────────────────────


class TestCronScheduling:
    def test_compute_next_run_daily(self):
        next_run = _compute_next_run("daily")
        assert next_run > datetime.now(UTC)

    def test_compute_next_run_weekly(self):
        next_run = _compute_next_run("weekly")
        assert next_run > datetime.now(UTC)

    def test_compute_next_run_monthly(self):
        next_run = _compute_next_run("monthly")
        assert next_run > datetime.now(UTC)

    def test_compute_next_run_custom(self):
        # Every hour at minute 0
        next_run = _compute_next_run("custom", "0 * * * *")
        assert next_run > datetime.now(UTC)

    def test_validate_valid_cron(self):
        assert validate_cron_expression("0 3 * * 1") is True
        assert validate_cron_expression("0 * * * *") is True
        assert validate_cron_expression("0 3 1 * *") is True

    def test_validate_invalid_cron(self):
        assert validate_cron_expression("not a cron") is False
        assert validate_cron_expression("") is False
        assert validate_cron_expression("* * *") is False


# ─── Rate Value Conversion ──────────────────────────────────────────


class TestRateValueConversion:
    """Test that AI rate values are correctly converted to DB format.

    AI returns human-readable percentages (5.875 = 5.875%).
    DB stores decimals (0.05875 for 5.875%).
    Flat rates are stored as-is.
    """

    def test_percentage_rate_converted(self):
        rate = AIExtractedRate(
            change_type="new",
            rate_type="percentage",
            rate_value=5.875,
            effective_start="2025-01-01",
            source_quote="Tax rate is 5.875%",
            confidence=0.9,
        )
        assert _convert_rate_value(rate) == pytest.approx(0.05875)

    def test_flat_rate_not_converted(self):
        rate = AIExtractedRate(
            change_type="new",
            rate_type="flat",
            rate_value=2.50,
            currency_code="USD",
            effective_start="2025-01-01",
            source_quote="Fee is $2.50",
            confidence=0.9,
        )
        assert _convert_rate_value(rate) == 2.50

    def test_tiered_rate_value_none(self):
        rate = AIExtractedRate(
            change_type="new",
            rate_type="tiered",
            rate_value=None,
            tiers=[{"min": 0, "max": 100, "rate_value": 2.0}],
            effective_start="2025-01-01",
            source_quote="Tiered rate",
            confidence=0.9,
        )
        assert _convert_rate_value(rate) is None

    def test_small_percentage_converted(self):
        rate = AIExtractedRate(
            change_type="new",
            rate_type="percentage",
            rate_value=0.375,
            effective_start="2025-01-01",
            source_quote="Surcharge is 0.375%",
            confidence=0.9,
        )
        assert _convert_rate_value(rate) == pytest.approx(0.00375)

    def test_large_percentage_converted(self):
        rate = AIExtractedRate(
            change_type="new",
            rate_type="percentage",
            rate_value=21.0,
            effective_start="2025-01-01",
            source_quote="VAT is 21%",
            confidence=0.9,
        )
        assert _convert_rate_value(rate) == pytest.approx(0.21)
