"""Prompts and schemas for the AI Triage agent.

The triage agent reviews a batch of pending approvals (draft rates, rules,
jurisdictions, detected_changes), verifies each against its cited source via
web_search, and either approves / rejects / defers each one to a human.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

# ─── Item type constants ──────────────────────────────────────────────

ItemType = Literal["rate", "rule", "jurisdiction", "change"]
ITEM_TYPES: tuple[ItemType, ...] = ("rate", "rule", "jurisdiction", "change")


# ─── Lightweight in-memory transport between runner and agent ────────


@dataclass
class PendingItem:
    """Snapshot of a pending item handed to the triage agent."""

    item_type: ItemType
    item_id: int
    jurisdiction_code: str | None
    jurisdiction_name: str | None
    summary: str  # one-line "what is being proposed"
    source_url: str | None
    source_quote: str | None
    authority_name: str | None
    legal_reference: str | None
    ai_confidence: float | None
    from_run_id: int | None
    extracted_data: dict | None


# ─── Action-tool input schemas (agent → handler) ─────────────────────


class ApproveItemInput(BaseModel):
    item_type: ItemType
    item_id: int
    reasoning: str = Field(min_length=20, max_length=800)
    confidence: float = Field(ge=0, le=1)
    source_verified_url: str = Field(min_length=4)


class RejectItemInput(BaseModel):
    item_type: ItemType
    item_id: int
    reasoning: str = Field(min_length=20, max_length=800)
    confidence: float = Field(ge=0, le=1)


class DeferItemInput(BaseModel):
    item_type: ItemType
    item_id: int
    reason: str = Field(min_length=10, max_length=400)


# ─── Decision record kept by the agent and applied by the runner ─────


class TriageDecision(BaseModel):
    item_type: ItemType
    item_id: int
    action: Literal["approved", "rejected", "deferred"]
    reasoning: str
    confidence: float | None = None
    source_verified_url: str | None = None


# ─── Exit tool ────────────────────────────────────────────────────────


class TriageReport(BaseModel):
    summary: str = Field(
        description="Brief summary of the batch: counts, notable patterns, anything operators should know."
    )
    items_reviewed: int = Field(
        ge=0,
        description="How many items you took a decision on (approve + reject + defer).",
    )


# ─── Prompt text ──────────────────────────────────────────────────────


TRIAGE_SYSTEM_PROMPT = """\
You are a tax-data triage agent. Humans wait in a queue to approve AI-detected
suggestions about accommodation/tourism tax rates and rules. Your job is to
remove the easy ones by VERIFYING each suggestion against its cited source and
either approving it, rejecting it, or — when in doubt — deferring it to a human.

## Tools you can use
- `web_search` — fetch the cited source URL or any related authoritative page.
  Verify the proposal against what the page actually says.
- `approve_item(item_type, item_id, reasoning, confidence, source_verified_url)`
  — call when the source clearly supports the suggestion.
- `reject_item(item_type, item_id, reasoning, confidence)` — call when the
  source clearly contradicts the suggestion, or the source is missing /
  broken / not authoritative.
- `defer_item(item_type, item_id, reason)` — call for anything you're unsure
  about. **This is the safe default. Be liberal with defers.**
- `report_triage_complete(summary, items_reviewed)` — call EXACTLY ONCE when
  you've finished the batch.

## Decision rules (HARD CONSTRAINTS — read carefully)

To **approve** an item, ALL of these MUST be true:
1. You fetched the cited `source_url` (or a clear authoritative substitute on
   the same official domain) via `web_search` in this run.
2. The numbers, dates, and text in the source MATCH the proposal exactly.
3. Your confidence is **≥ 0.9**.
4. You include `source_verified_url` = the URL you actually fetched.

To **reject** an item, ALL of these MUST be true:
1. Your confidence is **≥ 0.9** that the proposal is wrong, the source is
   broken / unrelated / non-authoritative, or no plausible source exists.
2. Your reasoning explains the specific contradiction or problem.

Anything else → **defer**. Defer means "a human should look at this." There is
no penalty for deferring. There is a large cost to wrongly approving.

## Anti-hallucination
- Every `item_id` you call a tool on MUST appear in the user prompt batch
  below. Never invent IDs.
- One decision per item. Don't approve then reject the same id.
- You cannot create new items, only act on the ones listed.

## Loop discipline
Work through the items one by one. For each:
1. Read the proposal and the source_quote.
2. If you need to verify, call `web_search` with a focused query.
3. Call exactly one of `approve_item` / `reject_item` / `defer_item`.

When every item has a decision (or you've spent too many turns and need to
defer the rest), call `report_triage_complete` ONCE with a brief summary and
the total `items_reviewed` count. Do not end your turn without calling it.
"""


def _fmt_optional(label: str, value) -> str:
    return f"  - {label}: {value}" if value not in (None, "", []) else ""


def build_triage_user_prompt(items: list[PendingItem]) -> str:
    """Render the batch as a numbered list the agent can iterate through."""
    if not items:
        return (
            "No pending items to triage. Call report_triage_complete with "
            "items_reviewed=0 to finish."
        )

    sections = [
        f"# Triage Batch ({len(items)} item{'s' if len(items) != 1 else ''})\n"
        f"Work through each item below. For each one, call exactly one of "
        f"approve_item / reject_item / defer_item using its `item_type` and "
        f"`item_id`. When done, call report_triage_complete."
    ]

    for i, item in enumerate(items, start=1):
        lines = [
            f"## Item {i} of {len(items)}",
            f"  - item_type: {item.item_type}",
            f"  - item_id: {item.item_id}",
        ]
        if item.jurisdiction_code:
            jname = item.jurisdiction_name or item.jurisdiction_code
            lines.append(f"  - jurisdiction: {item.jurisdiction_code} ({jname})")
        lines.append(f"  - proposed: {item.summary}")
        for label, value in [
            ("source_url", item.source_url),
            ("source_quote", item.source_quote),
            ("authority", item.authority_name),
            ("legal_reference", item.legal_reference),
            (
                "ai_confidence",
                f"{item.ai_confidence:.2f}" if item.ai_confidence is not None else None,
            ),
            ("from_agent_run", f"#{item.from_run_id}" if item.from_run_id else None),
        ]:
            line = _fmt_optional(label, value)
            if line:
                lines.append(line)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
