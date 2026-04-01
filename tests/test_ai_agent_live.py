"""
Live tests for the AI agent service.

These tests make REAL API calls to Anthropic and cost money.
Only run manually or in staging environments.

Run with: pytest tests/test_ai_agent_live.py -v -m live
"""

from unittest.mock import MagicMock

import pytest

from app.config import settings

# Skip entire module if no API key configured
pytestmark = pytest.mark.skipif(
    not settings.anthropic_api_key,
    reason="ANTHROPIC_API_KEY not configured — skipping live tests",
)


@pytest.mark.live
@pytest.mark.asyncio
async def test_agent_web_search_and_structured_output():
    """Test that the AI agent can search the web and return structured output."""
    from app.services.ai_agent_service import TaxMonitoringAgent
    from app.services.prompts.output_schema import AIMonitoringResult

    agent = TaxMonitoringAgent()

    # Create a mock jurisdiction
    jurisdiction = MagicMock()
    jurisdiction.code = "US-NY-NYC"
    jurisdiction.name = "New York City"
    jurisdiction.jurisdiction_type = "city"
    jurisdiction.country_code = "US"
    jurisdiction.currency_code = "USD"
    jurisdiction.path = "US.NY.NYC"
    jurisdiction.local_name = None

    result = await agent.research_jurisdiction(
        jurisdiction=jurisdiction,
        current_rates=[],
        current_rules=[],
        monitored_urls=["https://www.nyc.gov/site/finance/taxes/hotel-room-occupancy-tax.page"],
    )

    # Validate structured output
    assert isinstance(result, AIMonitoringResult)
    assert result.jurisdiction_code == "US-NY-NYC"
    assert len(result.summary) > 0
    assert 0.0 <= result.overall_confidence <= 1.0

    # Should have found at least some rates for NYC
    assert len(result.rates) > 0, "Expected at least one tax rate for NYC"
    assert len(result.sources_checked) > 0, "Expected at least one source checked"

    # Validate first rate structure
    rate = result.rates[0]
    assert rate.change_type in ("new", "changed", "unchanged", "removed")
    assert rate.rate_type in ("percentage", "flat", "tiered")
    assert len(rate.source_quote) > 0
    assert 0.0 <= rate.confidence <= 1.0

    print(f"\nAI Agent Result for {result.jurisdiction_code}:")
    print(f"  Summary: {result.summary}")
    print(f"  Rates found: {len(result.rates)}")
    print(f"  Rules found: {len(result.rules)}")
    print(f"  Sources checked: {len(result.sources_checked)}")
    print(f"  Overall confidence: {result.overall_confidence:.2f}")
    for r in result.rates:
        print(f"  Rate: {r.tax_category_code} / {r.rate_type} = {r.rate_value} ({r.change_type}, {r.confidence:.2f})")
    for r in result.rules:
        print(f"  Rule: {r.name} / {r.rule_type} ({r.change_type}, {r.confidence:.2f})")


@pytest.mark.live
@pytest.mark.asyncio
async def test_agent_handles_unknown_jurisdiction():
    """Test agent gracefully handles a jurisdiction with minimal info."""
    from app.services.ai_agent_service import TaxMonitoringAgent
    from app.services.prompts.output_schema import AIMonitoringResult

    agent = TaxMonitoringAgent()

    jurisdiction = MagicMock()
    jurisdiction.code = "XX-TEST"
    jurisdiction.name = "Test Unknown Jurisdiction"
    jurisdiction.jurisdiction_type = "city"
    jurisdiction.country_code = "XX"
    jurisdiction.currency_code = "XXX"
    jurisdiction.path = "XX"
    jurisdiction.local_name = None

    result = await agent.research_jurisdiction(
        jurisdiction=jurisdiction,
        current_rates=[],
        current_rules=[],
        monitored_urls=[],
    )

    assert isinstance(result, AIMonitoringResult)
    assert result.jurisdiction_code == "XX-TEST"
    # For an unknown jurisdiction, confidence should be low
    assert result.overall_confidence < 0.8

    print(f"\nUnknown jurisdiction result: {result.summary}")
    print(f"  Confidence: {result.overall_confidence:.2f}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_structured_output_schema_validation():
    """Test that the Anthropic API accepts our schema and returns valid data."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    from app.services.prompts.output_schema import AIMonitoringResult

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": (
                "You are testing a tax monitoring system. Return a sample result "
                "for New York City with 2 tax rates and 1 exemption rule. "
                "Use realistic values. Call the report_tax_findings tool."
            ),
        }],
        tools=[{
            "name": "report_tax_findings",
            "description": "Report tax findings",
            "input_schema": AIMonitoringResult.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "report_tax_findings"},
    )

    # Find the tool_use block
    tool_block = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "report_tax_findings":
            tool_block = block
            break

    assert tool_block is not None, f"No tool_use block found. Stop reason: {response.stop_reason}"

    # Parse and validate
    result = AIMonitoringResult.model_validate(tool_block.input)
    assert result.jurisdiction_code is not None
    assert len(result.rates) >= 1
    assert result.overall_confidence > 0

    print("\nSchema validation test passed:")
    print(f"  Rates: {len(result.rates)}")
    print(f"  Rules: {len(result.rules)}")
    print(f"  Confidence: {result.overall_confidence:.2f}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_rate_value_conversion_with_real_data():
    """Test that AI-returned rate values convert correctly to DB format.

    The AI returns human-readable percentages (5.875 = 5.875%).
    The DB stores decimals (0.05875). This test validates the conversion.
    """
    from app.services.ai_agent_service import TaxMonitoringAgent
    from app.services.change_detection_service import _convert_rate_value

    agent = TaxMonitoringAgent()

    jurisdiction = MagicMock()
    jurisdiction.code = "US-NY-NYC"
    jurisdiction.name = "New York City"
    jurisdiction.jurisdiction_type = "city"
    jurisdiction.country_code = "US"
    jurisdiction.currency_code = "USD"
    jurisdiction.path = "US.NY.NYC"
    jurisdiction.local_name = None

    result = await agent.research_jurisdiction(
        jurisdiction=jurisdiction,
        current_rates=[],
        current_rules=[],
        monitored_urls=["https://www.nyc.gov/site/finance/taxes/hotel-room-occupancy-tax.page"],
    )

    # Validate rate value conversion for each percentage rate
    for rate in result.rates:
        db_value = _convert_rate_value(rate)
        if rate.rate_type == "percentage" and rate.rate_value is not None:
            # AI returns 5.875, DB should store 0.05875
            assert db_value < 1.0, (
                f"Percentage rate {rate.rate_value} should convert to < 1.0 "
                f"but got {db_value}"
            )
            assert db_value == rate.rate_value / 100.0
            print(f"  Rate {rate.tax_category_code}: AI={rate.rate_value}% → DB={db_value:.6f}")
        elif rate.rate_type == "flat" and rate.rate_value is not None:
            # Flat rates stored as-is
            assert db_value == rate.rate_value
            print(f"  Flat {rate.tax_category_code}: AI=${rate.rate_value} → DB={db_value}")

    print(f"\nRate conversion test passed for {len(result.rates)} rates")
