"""AgentRunRecorder — captures per-turn telemetry from agent loops.

Usage:
    recorder = AgentRunRecorder(
        model=settings.anthropic_model,
        system_prompt=SYSTEM_PROMPT,
        initial_user_prompt=user_prompt,
    )

    # In each agent turn, after calling the API:
    recorder.record_turn(
        response=response,
        started_at=t0,
        completed_at=t1,
        request_messages=messages_sent,
    )

    # After the agent returns (or raises):
    await recorder.flush(db, job.id)

flush() writes one row per turn into agent_run_turns AND updates the
aggregate columns + estimated_cost_usd on the owning MonitoringJob.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run_turn import AgentRunTurn
from app.models.monitoring_job import MonitoringJob
from app.services.pricing import compute_cost

logger = logging.getLogger(__name__)

# Cap any single content block's text payload at this many characters
# before storing — protects against runaway web-search payloads. The DB
# can hold a lot, but the UI doesn't need megabytes per block.
_MAX_TEXT_BLOCK_CHARS = 16_000


@dataclass
class TurnRecord:
    turn_index: int
    model: str
    stop_reason: str | None
    request_messages: list
    response_content: list
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    web_search_count: int
    latency_ms: int
    started_at: datetime
    completed_at: datetime


def _content_block_to_jsonable(block: Any) -> dict:
    """Convert an anthropic content block (pydantic v2) to plain JSON."""
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", exclude_none=True)
    if isinstance(block, dict):
        return block
    # Fall back: stringify
    return {"type": "unknown", "repr": repr(block)}


def _truncate_text_blocks(blocks: list[dict]) -> list[dict]:
    """Truncate large text fields in-place (on a deep copy) for storage."""
    out: list[dict] = []
    for block in blocks:
        copied = copy.deepcopy(block)
        text = copied.get("text")
        if isinstance(text, str) and len(text) > _MAX_TEXT_BLOCK_CHARS:
            copied["text"] = (
                text[:_MAX_TEXT_BLOCK_CHARS]
                + f"\n…[truncated {len(text) - _MAX_TEXT_BLOCK_CHARS} chars]"
            )
        # Web search results: each citation has a snippet — same treatment
        if copied.get("type") == "web_search_tool_result":
            content = copied.get("content")
            if isinstance(content, list):
                for hit in content:
                    if not isinstance(hit, dict):
                        continue
                    snippet = hit.get("encrypted_content") or hit.get("snippet")
                    if isinstance(snippet, str) and len(snippet) > _MAX_TEXT_BLOCK_CHARS:
                        key = "encrypted_content" if "encrypted_content" in hit else "snippet"
                        hit[key] = (
                            snippet[:_MAX_TEXT_BLOCK_CHARS]
                            + f"\n…[truncated {len(snippet) - _MAX_TEXT_BLOCK_CHARS} chars]"
                        )
        out.append(copied)
    return out


def _normalize_messages(messages: list) -> list:
    """Convert anything in `messages` to plain JSON; truncate big text."""
    normalized: list = []
    for msg in messages:
        if not isinstance(msg, dict):
            normalized.append({"role": "unknown", "repr": repr(msg)})
            continue
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            normalized.append({"role": role, "content": content})
        elif isinstance(content, list):
            blocks = [_content_block_to_jsonable(b) for b in content]
            normalized.append({"role": role, "content": _truncate_text_blocks(blocks)})
        else:
            normalized.append({"role": role, "content": content})
    return normalized


def _count_web_searches(response_content: list[dict]) -> int:
    """Count server_tool_use blocks with name == 'web_search' in a response."""
    count = 0
    for block in response_content:
        if (
            block.get("type") == "server_tool_use"
            and block.get("name") == "web_search"
        ):
            count += 1
    return count


class AgentRunRecorder:
    """Collects per-turn data during an agent run and flushes to DB at the end."""

    def __init__(self, *, model: str, system_prompt: str, initial_user_prompt: str) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.initial_user_prompt = initial_user_prompt
        self.turns: list[TurnRecord] = []

    def record_turn(
        self,
        *,
        response: Any,  # anthropic.types.Message
        started_at: datetime,
        completed_at: datetime,
        request_messages: list,
    ) -> None:
        """Record one turn. Safe to call from inside the agent loop."""
        response_content = [
            _content_block_to_jsonable(b) for b in (response.content or [])
        ]
        response_content = _truncate_text_blocks(response_content)

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        web_searches = _count_web_searches(response_content)

        latency_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))

        turn = TurnRecord(
            turn_index=len(self.turns),
            model=getattr(response, "model", None) or self.model,
            stop_reason=getattr(response, "stop_reason", None),
            request_messages=_normalize_messages(request_messages),
            response_content=response_content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            web_search_count=web_searches,
            latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.turns.append(turn)

    async def flush(self, db: AsyncSession, monitoring_job_id: int) -> None:
        """Persist all turns and update aggregate fields on the owning job.

        Idempotent-ish: if called twice, the unique constraint
        (monitoring_job_id, turn_index) would conflict. Callers should
        avoid double-flushing.
        """
        # 1. Insert turn rows
        for t in self.turns:
            db.add(
                AgentRunTurn(
                    monitoring_job_id=monitoring_job_id,
                    turn_index=t.turn_index,
                    model=t.model,
                    stop_reason=t.stop_reason,
                    request_messages=t.request_messages,
                    response_content=t.response_content,
                    input_tokens=t.input_tokens,
                    output_tokens=t.output_tokens,
                    cache_creation_input_tokens=t.cache_creation_input_tokens,
                    cache_read_input_tokens=t.cache_read_input_tokens,
                    web_search_count=t.web_search_count,
                    latency_ms=t.latency_ms,
                    started_at=t.started_at,
                    completed_at=t.completed_at,
                )
            )

        # 2. Aggregate totals
        totals = {
            "total_input_tokens": sum(t.input_tokens for t in self.turns),
            "total_output_tokens": sum(t.output_tokens for t in self.turns),
            "total_cache_creation_tokens": sum(t.cache_creation_input_tokens for t in self.turns),
            "total_cache_read_tokens": sum(t.cache_read_input_tokens for t in self.turns),
            "total_web_search_count": sum(t.web_search_count for t in self.turns),
        }
        cost = compute_cost(
            self.model,
            input_tokens=totals["total_input_tokens"],
            output_tokens=totals["total_output_tokens"],
            cache_creation_tokens=totals["total_cache_creation_tokens"],
            cache_read_tokens=totals["total_cache_read_tokens"],
            web_search_count=totals["total_web_search_count"],
        )

        # 3. Update the job row
        job = await db.get(MonitoringJob, monitoring_job_id)
        if job is None:
            logger.error(
                "AgentRunRecorder.flush: job %d disappeared before flush; "
                "turns will still be inserted but aggregate metrics lost.",
                monitoring_job_id,
            )
            return

        job.model = self.model
        job.system_prompt = self.system_prompt
        job.initial_user_prompt = self.initial_user_prompt
        for k, v in totals.items():
            setattr(job, k, v)
        job.estimated_cost_usd = cost

        await db.flush()
        logger.info(
            "Recorded %d turns for job %d — tokens in=%d out=%d searches=%d cost=$%s",
            len(self.turns), monitoring_job_id,
            totals["total_input_tokens"], totals["total_output_tokens"],
            totals["total_web_search_count"], cost,
        )
