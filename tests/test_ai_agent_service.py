"""
Unit tests for the AI agent service using mocked Anthropic client.

These tests do NOT call the real API — they mock the Anthropic client
to verify the agentic loop logic, retry behavior, and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from app.services.prompts.output_schema import AIMonitoringResult


def _make_jurisdiction():
    j = MagicMock()
    j.code = "US-NY-NYC"
    j.name = "New York City"
    j.jurisdiction_type = "city"
    j.country_code = "US"
    j.currency_code = "USD"
    j.path = "US.NY.NYC"
    j.local_name = None
    return j


def _make_tool_use_block(name, input_data, block_id="tool_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = block_id
    block.input = input_data
    return block


def _make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(content, stop_reason="end_turn"):
    resp = MagicMock()
    resp.content = content
    resp.stop_reason = stop_reason
    resp.usage = MagicMock()
    resp.usage.input_tokens = 100
    resp.usage.output_tokens = 50
    return resp


def _valid_report_input():
    return {
        "jurisdiction_code": "US-NY-NYC",
        "summary": "NYC has an occupancy tax of 5.875%.",
        "rates": [
            {
                "change_type": "unchanged",
                "rate_type": "percentage",
                "rate_value": 5.875,
                "effective_start": "2024-01-01",
                "source_quote": "The tax rate is 5.875%.",
                "confidence": 0.95,
            }
        ],
        "rules": [],
        "sources_checked": ["https://nyc.gov"],
        "overall_confidence": 0.95,
    }


class TestTaxMonitoringAgentInit:
    def test_raises_without_api_key(self):
        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            from app.services.ai_agent_service import TaxMonitoringAgent
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                TaxMonitoringAgent()


class TestResearchJurisdiction:
    @pytest.mark.asyncio
    async def test_report_on_first_turn(self):
        """Agent calls report_tax_findings immediately -> returns result."""
        report_block = _make_tool_use_block("report_tax_findings", _valid_report_input())
        response = _make_response([report_block], stop_reason="tool_use")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60
            mock_settings.anthropic_max_search_uses = 10
            mock_settings.anthropic_max_agent_turns = 20

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            agent._call_api = AsyncMock(return_value=response)

            result = await agent.research_jurisdiction(
                _make_jurisdiction(), [], [], []
            )

            assert isinstance(result, AIMonitoringResult)
            assert result.jurisdiction_code == "US-NY-NYC"
            assert len(result.rates) == 1
            agent._call_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_web_search_then_report(self):
        """Agent does web_search first, then reports on second turn."""
        search_block = _make_tool_use_block("web_search", {"query": "NYC tax"})
        search_resp = _make_response([search_block], stop_reason="tool_use")

        report_block = _make_tool_use_block("report_tax_findings", _valid_report_input())
        report_resp = _make_response([report_block], stop_reason="tool_use")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60
            mock_settings.anthropic_max_search_uses = 10
            mock_settings.anthropic_max_agent_turns = 20

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            agent._call_api = AsyncMock(side_effect=[search_resp, report_resp])

            result = await agent.research_jurisdiction(
                _make_jurisdiction(), [], [], []
            )

            assert isinstance(result, AIMonitoringResult)
            assert agent._call_api.call_count == 2

    @pytest.mark.asyncio
    async def test_end_turn_nudge_then_report(self):
        """Agent returns end_turn -> nudge message sent -> agent reports."""
        text_block = _make_text_block("I found the tax info.")
        end_resp = _make_response([text_block], stop_reason="end_turn")

        report_block = _make_tool_use_block("report_tax_findings", _valid_report_input())
        report_resp = _make_response([report_block], stop_reason="tool_use")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60
            mock_settings.anthropic_max_search_uses = 10
            mock_settings.anthropic_max_agent_turns = 20

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            agent._call_api = AsyncMock(side_effect=[end_resp, report_resp])

            result = await agent.research_jurisdiction(
                _make_jurisdiction(), [], [], []
            )
            assert isinstance(result, AIMonitoringResult)
            # Second call should include the nudge message
            assert agent._call_api.call_count == 2

    @pytest.mark.asyncio
    async def test_max_turns_exceeded_raises(self):
        """Agent exhausts max_turns without reporting -> RuntimeError."""
        text_block = _make_text_block("Still searching...")
        end_resp = _make_response([text_block], stop_reason="end_turn")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60
            mock_settings.anthropic_max_search_uses = 10
            mock_settings.anthropic_max_agent_turns = 3

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            agent._call_api = AsyncMock(return_value=end_resp)

            with pytest.raises(RuntimeError, match="exhausted"):
                await agent.research_jurisdiction(
                    _make_jurisdiction(), [], [], []
                )
            assert agent._call_api.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_report_output_raises(self):
        """Agent returns invalid structured output -> ValueError."""
        bad_block = _make_tool_use_block("report_tax_findings", {"bad": "data"})
        response = _make_response([bad_block], stop_reason="tool_use")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60
            mock_settings.anthropic_max_search_uses = 10
            mock_settings.anthropic_max_agent_turns = 20

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            agent._call_api = AsyncMock(return_value=response)

            with pytest.raises(ValueError, match="invalid structured output"):
                await agent.research_jurisdiction(
                    _make_jurisdiction(), [], [], []
                )


class TestCallApiRetry:
    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self):
        """Rate limit errors are retried with backoff."""
        mock_response = _make_response([], stop_reason="end_turn")

        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()

            mock_create = AsyncMock(side_effect=[
                anthropic.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                mock_response,
            ])
            agent.client.messages.create = mock_create

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await agent._call_api(
                    [{"role": "user", "content": "test"}], []
                )

            assert result == mock_response
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_4xx_immediately(self):
        """4xx errors (non-rate-limit) are NOT retried."""
        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()

            agent.client.messages.create = AsyncMock(side_effect=anthropic.APIStatusError(
                message="bad request",
                response=MagicMock(status_code=400),
                body=None,
            ))

            with pytest.raises(anthropic.APIStatusError):
                await agent._call_api(
                    [{"role": "user", "content": "test"}], []
                )

            # Should NOT retry
            assert agent.client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        """After MAX_RETRIES, raises RuntimeError."""
        with patch("app.services.ai_agent_service.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.anthropic_max_tokens = 4096
            mock_settings.anthropic_timeout_seconds = 60

            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()

            agent.client.messages.create = AsyncMock(
                side_effect=anthropic.APIConnectionError(request=MagicMock())
            )

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="failed after"):
                    await agent._call_api(
                        [{"role": "user", "content": "test"}], []
                    )

            assert agent.client.messages.create.call_count == 3  # MAX_RETRIES
