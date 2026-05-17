"""AI Triage agent.

Reviews a batch of pending approvals (rates, rules, jurisdictions, detected
changes), verifies each against its source URL via web_search, and queues an
approve / reject / defer decision for each one. The runner applies the
queued decisions atomically after the loop completes.
"""
from __future__ import annotations

import logging
from typing import ClassVar

from pydantic import ValidationError

from app.services.agents.base import ActionToolDef, BaseAnthropicAgent
from app.services.prompts.triage import (
    TRIAGE_SYSTEM_PROMPT,
    ApproveItemInput,
    DeferItemInput,
    RejectItemInput,
    TriageDecision,
    TriageReport,
)

logger = logging.getLogger(__name__)


def _strip_defs_descriptions(schema: dict) -> dict:
    """Anthropic accepts JSON schema input_schema as-is; nothing to strip."""
    return schema


class TriageAgent(BaseAnthropicAgent):
    """Triage agent — see app/services/prompts/triage.py for the system prompt."""

    name: ClassVar[str] = "triage"
    system_prompt: ClassVar[str] = TRIAGE_SYSTEM_PROMPT
    report_tool_name: ClassVar[str] = "report_triage_complete"
    report_tool_description: ClassVar[str] = (
        "Report that you have finished triaging the batch. Call this tool "
        "exactly once when you've taken a decision on every item (or decided "
        "to defer the remainder). Include a brief summary."
    )
    result_model: ClassVar[type] = TriageReport
    # Triage runs may need to verify many items; raise the cap accordingly.
    # Stay under Anthropic's 50-per-request hard limit.
    max_search_uses: ClassVar[int | None] = 40

    action_tools: ClassVar[list[ActionToolDef]] = [
        {
            "name": "approve_item",
            "description": (
                "Approve a pending item. Use ONLY when you have verified the "
                "proposal against its cited source via web_search AND your "
                "confidence is ≥ 0.9. You MUST set source_verified_url to the "
                "URL you actually fetched."
            ),
            "input_schema": _strip_defs_descriptions(ApproveItemInput.model_json_schema()),
        },
        {
            "name": "reject_item",
            "description": (
                "Reject a pending item. Use ONLY when you are ≥ 0.9 confident "
                "that the proposal is wrong, the source is broken / unrelated / "
                "non-authoritative, or no plausible source exists."
            ),
            "input_schema": _strip_defs_descriptions(RejectItemInput.model_json_schema()),
        },
        {
            "name": "defer_item",
            "description": (
                "Defer a pending item to a human reviewer. Use this for anything "
                "you are not confident about. There is no penalty for deferring."
            ),
            "input_schema": _strip_defs_descriptions(DeferItemInput.model_json_schema()),
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        # Decisions queued during the loop; runner applies them after.
        self.decisions: list[TriageDecision] = []

    async def _handle_action_tool(self, name: str, tool_input: dict) -> str:
        try:
            if name == "approve_item":
                v = ApproveItemInput.model_validate(tool_input)
                self.decisions.append(
                    TriageDecision(
                        item_type=v.item_type,
                        item_id=v.item_id,
                        action="approved",
                        reasoning=v.reasoning,
                        confidence=v.confidence,
                        source_verified_url=v.source_verified_url,
                    )
                )
                return (
                    f"Queued APPROVE for {v.item_type}#{v.item_id} "
                    f"(confidence {v.confidence:.2f}). "
                    f"Decisions so far: {len(self.decisions)}."
                )
            if name == "reject_item":
                v = RejectItemInput.model_validate(tool_input)
                self.decisions.append(
                    TriageDecision(
                        item_type=v.item_type,
                        item_id=v.item_id,
                        action="rejected",
                        reasoning=v.reasoning,
                        confidence=v.confidence,
                    )
                )
                return (
                    f"Queued REJECT for {v.item_type}#{v.item_id} "
                    f"(confidence {v.confidence:.2f}). "
                    f"Decisions so far: {len(self.decisions)}."
                )
            if name == "defer_item":
                v = DeferItemInput.model_validate(tool_input)
                self.decisions.append(
                    TriageDecision(
                        item_type=v.item_type,
                        item_id=v.item_id,
                        action="deferred",
                        reasoning=v.reason,
                    )
                )
                return (
                    f"Queued DEFER for {v.item_type}#{v.item_id}. "
                    f"Decisions so far: {len(self.decisions)}."
                )
            return f"Unknown action tool: {name}"
        except ValidationError as e:
            # The model sees this as the tool_result and can self-correct.
            logger.warning("Triage tool %s input invalid: %s", name, e)
            return (
                f"Invalid input for {name}: {e.errors()[0]['msg'] if e.errors() else e}. "
                f"Check the required fields and try again."
            )
