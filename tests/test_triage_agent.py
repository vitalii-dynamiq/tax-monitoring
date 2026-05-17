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


class TestMaxTurnsOverride:
    def test_triage_agent_overrides_max_turns_to_50(self):
        """Per-agent max_turns override is respected over the global default."""
        from app.services.agents.triage import TriageAgent

        assert TriageAgent.max_turns == 50

    @pytest.mark.asyncio
    async def test_max_turns_override_used_in_loop(self):
        """The loop respects the agent's max_turns rather than the global setting."""
        text = MagicMock()
        text.type = "text"
        text.text = "still thinking"
        resp = _resp([text], stop_reason="end_turn")

        with patch("app.services.agents.base.settings") as mock_settings:
            _patch_settings(mock_settings)
            mock_settings.anthropic_max_agent_turns = 100  # global is huge
            from app.services.agents.triage import TriageAgent

            agent = TriageAgent()  # but agent's own max_turns=50
            # No decisions queued — fallback returns None, base raises
            agent._call_api = AsyncMock(return_value=resp)

            with pytest.raises(RuntimeError, match="exhausted 50 turns"):
                await agent.run(user_prompt="x")
            assert agent._call_api.call_count == 50


class TestLoopExhaustedFallback:
    @pytest.mark.asyncio
    async def test_exhausted_with_decisions_returns_fallback_report(self):
        """If the agent decided on items but never called report, we synthesize a report."""
        from app.services.agents.triage import TriageAgent
        from app.services.prompts.output_schema import AIMonitoringResult  # not used; just imports check
        del AIMonitoringResult

        text = MagicMock()
        text.type = "text"
        text.text = "thinking"
        resp = _resp([text], stop_reason="end_turn")

        with patch("app.services.agents.base.settings") as mock_settings:
            _patch_settings(mock_settings)
            mock_settings.anthropic_max_agent_turns = 3
            from app.services.prompts.triage import TriageDecision

            agent = TriageAgent(batch_size=10)
            # Pre-seed decisions (simulating mid-loop progress)
            agent.decisions = [
                TriageDecision(
                    item_type="rate", item_id=i, action="approved",
                    reasoning="ok", confidence=0.95,
                    source_verified_url="https://x.gov",
                )
                for i in range(3)
            ]
            # Make the agent override max_turns=3 (avoid 50)
            type(agent).max_turns = 3  # temporary patch
            try:
                agent._call_api = AsyncMock(return_value=resp)
                report = await agent.run(user_prompt="x")
            finally:
                type(agent).max_turns = 50  # restore

            assert report.items_reviewed == 3
            assert "max-turn cap" in report.summary

    @pytest.mark.asyncio
    async def test_exhausted_with_no_decisions_still_raises(self):
        """Empty-decisions exhaustion preserves the loud RuntimeError."""
        text = MagicMock()
        text.type = "text"
        text.text = "thinking"
        resp = _resp([text], stop_reason="end_turn")

        with patch("app.services.agents.base.settings") as mock_settings:
            _patch_settings(mock_settings)
            mock_settings.anthropic_max_agent_turns = 2
            from app.services.agents.triage import TriageAgent

            agent = TriageAgent()
            type(agent).max_turns = 2
            try:
                agent._call_api = AsyncMock(return_value=resp)
                with pytest.raises(RuntimeError, match="exhausted"):
                    await agent.run(user_prompt="x")
            finally:
                type(agent).max_turns = 50


class TestProgressNudge:
    @pytest.mark.asyncio
    async def test_progress_suffix_reports_n_of_batch(self):
        """Tool results progressively show N/batch_size and a final nudge."""
        from app.services.agents.triage import TriageAgent

        agent = TriageAgent(batch_size=2)
        # First decision: 1/2
        msg1 = await agent._handle_action_tool(
            "approve_item",
            {
                "item_type": "rate", "item_id": 100,
                "reasoning": "Source matches the proposal exactly.",
                "confidence": 0.95, "source_verified_url": "https://x.gov",
            },
        )
        assert "1/2" in msg1
        assert "ALL ITEMS DECIDED" not in msg1
        # Second: 2/2 with nudge
        msg2 = await agent._handle_action_tool(
            "defer_item",
            {"item_type": "rate", "item_id": 101, "reason": "Source ambiguous."},
        )
        assert "2/2" in msg2
        assert "ALL ITEMS DECIDED" in msg2
        assert "report_triage_complete" in msg2
