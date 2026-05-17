"""Unit tests for TriageAgent's action-tool dispatch with a mocked Anthropic client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patch_settings(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    mock_settings.anthropic_model = "claude-sonnet-4-6"
    mock_settings.anthropic_max_tokens = 4096
    mock_settings.anthropic_timeout_seconds = 60
    mock_settings.anthropic_max_search_uses = 10
    mock_settings.anthropic_max_agent_turns = 20


def _block(type_, **kw):
    b = MagicMock()
    b.type = type_
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def _tool_use(name, input_, block_id="t1"):
    return _block("tool_use", name=name, id=block_id, input=input_)


def _text(text):
    return _block("text", text=text)


def _resp(content, stop_reason="tool_use"):
    r = MagicMock()
    r.content = content
    r.stop_reason = stop_reason
    r.usage = MagicMock(input_tokens=100, output_tokens=20)
    return r


class TestTriageActionTools:
    @pytest.mark.asyncio
    async def test_full_loop_queues_decisions_and_exits(self):
        # Turn 1: agent calls approve_item + defer_item
        # Turn 2: agent calls reject_item
        # Turn 3: agent calls report_triage_complete → loop exits
        approve_input = {
            "item_type": "rate",
            "item_id": 100,
            "reasoning": "Source clearly states 5.875% rate effective 2024-01-01. Matches.",
            "confidence": 0.95,
            "source_verified_url": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
        }
        defer_input = {
            "item_type": "jurisdiction",
            "item_id": 200,
            "reason": "Source URL unreachable; can't verify the claim.",
        }
        reject_input = {
            "item_type": "rule",
            "item_id": 300,
            "reasoning": "Source explicitly contradicts: exemption removed 2023-12.",
            "confidence": 0.92,
        }
        report_input = {"summary": "3 items reviewed", "items_reviewed": 3}

        turn1 = _resp([
            _text("Reviewing item 100 and 200..."),
            _tool_use("approve_item", approve_input, "tu1"),
            _tool_use("defer_item", defer_input, "tu2"),
        ])
        turn2 = _resp([_tool_use("reject_item", reject_input, "tu3")])
        turn3 = _resp([_tool_use("report_triage_complete", report_input, "tu4")])

        with patch("app.services.agents.base.settings") as mock_settings:
            _patch_settings(mock_settings)
            from app.services.agents.triage import TriageAgent

            agent = TriageAgent()
            agent._call_api = AsyncMock(side_effect=[turn1, turn2, turn3])

            report = await agent.run(user_prompt="batch of 3 items")

            assert report.items_reviewed == 3
            assert len(agent.decisions) == 3
            actions = [d.action for d in agent.decisions]
            assert sorted(actions) == ["approved", "deferred", "rejected"]
            # The approval decision carries the verified URL
            approval = next(d for d in agent.decisions if d.action == "approved")
            assert approval.source_verified_url.startswith("https://www.nyc.gov")
            assert approval.item_id == 100

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_error_to_model(self):
        """A malformed action-tool call doesn't crash — the model gets an error
        string back as a tool_result so it can self-correct."""
        bad_input = {
            "item_type": "rate",
            "item_id": 50,
            # missing reasoning + confidence + source_verified_url
        }
        report_input = {"summary": "did nothing", "items_reviewed": 0}

        turn1 = _resp([_tool_use("approve_item", bad_input, "tu1")])
        turn2 = _resp([_tool_use("report_triage_complete", report_input, "tu2")])

        with patch("app.services.agents.base.settings") as mock_settings:
            _patch_settings(mock_settings)
            from app.services.agents.triage import TriageAgent

            agent = TriageAgent()
            agent._call_api = AsyncMock(side_effect=[turn1, turn2])

            report = await agent.run(user_prompt="batch")
            assert report.items_reviewed == 0
            assert agent.decisions == []  # nothing queued — payload rejected
