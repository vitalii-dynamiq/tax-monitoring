"""BaseAnthropicAgent — shared agentic-loop scaffold for all Anthropic-backed agents.

Subclasses provide:
  - `name`: registry key
  - `system_prompt`: str  (or class property)
  - `report_tool_name`: name of the custom tool the agent must call to finish
  - `result_model`: Pydantic class to validate the report tool's input against

The base owns:
  - Client instantiation (anthropic.AsyncAnthropic)
  - The agentic loop: web_search + report tool, with retry on transient errors
  - The recorder hook (AgentRunRecorder) so per-turn telemetry is uniform

Adding a new agent = one file + one line in __init__.AGENTS.
Replacing one with an external runner = a sibling class that exposes .run() with
the same signature; the registry doesn't care about the parent class.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, TypedDict

import anthropic
from pydantic import BaseModel

from app.config import settings

if TYPE_CHECKING:
    from app.services.agent_run_recorder import AgentRunRecorder

logger = logging.getLogger(__name__)

# Retry config for transient API errors
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


class ActionToolDef(TypedDict):
    """A custom in-loop tool the agent can call any number of times.

    Unlike the report tool (which terminates the loop), action tools are handled
    via `_handle_action_tool` and the loop continues. Use them for per-item
    actions like "approve this rate" / "defer that change".
    """

    name: str
    description: str
    input_schema: dict


class BaseAnthropicAgent(ABC):
    """Common scaffolding for agentic Claude runs with web search + custom report tool."""

    # ─── Subclass contract ────────────────────────────────────────────
    name: ClassVar[str]
    system_prompt: ClassVar[str]
    report_tool_name: ClassVar[str]
    report_tool_description: ClassVar[str]
    result_model: ClassVar[type[BaseModel]]
    # Optional: action tools the agent can invoke during the loop. Each
    # tool_use block matching a name here is dispatched to `_handle_action_tool`.
    action_tools: ClassVar[list[ActionToolDef]] = []
    # Optional: override the web_search max_uses for this agent.
    max_search_uses: ClassVar[int | None] = None

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. "
                "Set it in .env or environment variables."
            )
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # ─── Public API ──────────────────────────────────────────────────

    async def run(
        self,
        *,
        user_prompt: str,
        recorder: AgentRunRecorder | None = None,
        log_label: str = "",
    ) -> BaseModel:
        """Run the agentic loop. Returns the validated result_model.

        `recorder` (if supplied) captures every turn (system+user prompt are
        passed in separately when the recorder is built).
        `log_label` is prefixed to log messages for traceability.
        """
        tools = self._build_tools()
        messages: list[dict] = [{"role": "user", "content": user_prompt}]
        max_turns = settings.anthropic_max_agent_turns

        logger.info(
            "%sStarting %s agent (model=%s, max_turns=%d, max_searches=%d)",
            f"[{log_label}] " if log_label else "",
            self.name,
            settings.anthropic_model,
            max_turns,
            settings.anthropic_max_search_uses,
        )

        last_response = None
        for turn in range(max_turns):
            t_start = datetime.now(UTC)
            request_snapshot = list(messages)
            response = await self._call_api(messages, tools)
            t_end = datetime.now(UTC)
            last_response = response

            if recorder is not None:
                try:
                    recorder.record_turn(
                        response=response,
                        started_at=t_start,
                        completed_at=t_end,
                        request_messages=request_snapshot,
                    )
                except Exception:
                    logger.warning("recorder.record_turn failed", exc_info=True)

            tool_calls = [b.name for b in response.content if b.type == "tool_use"]
            logger.info(
                "%sTurn %d: stop=%s tools=%s tokens=%s/%s",
                f"[{log_label}] " if log_label else "",
                turn + 1,
                response.stop_reason,
                tool_calls or "none",
                getattr(response.usage, "input_tokens", "?"),
                getattr(response.usage, "output_tokens", "?"),
            )

            # Did the agent call our custom report tool? If so, we're done.
            for block in response.content:
                if block.type == "tool_use" and block.name == self.report_tool_name:
                    try:
                        return self.result_model.model_validate(block.input)
                    except Exception as e:
                        logger.error(
                            "Failed to parse %s output: %s\nRaw input: %s",
                            self.report_tool_name, e, block.input,
                        )
                        raise ValueError(
                            f"AI returned invalid structured output: {e}"
                        ) from e

            # Otherwise: nudge or continue based on stop_reason
            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"You have finished your research. Now call the "
                        f"{self.report_tool_name} tool with your complete findings."
                    ),
                })
                continue

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                # Reply to any non-server tool calls. web_search is server-side
                # (Anthropic auto-injects results). The report tool exits the
                # loop above. Action tools we dispatch to the subclass hook;
                # anything else gets a "not available" response.
                action_names = {a["name"] for a in self.action_tools}
                tool_results = []
                for block in response.content:
                    if (
                        block.type == "tool_use"
                        and block.name not in (self.report_tool_name, "web_search")
                    ):
                        if block.name in action_names:
                            try:
                                content = await self._handle_action_tool(
                                    block.name, block.input
                                )
                            except Exception as e:
                                logger.warning(
                                    "Action tool %s raised: %s", block.name, e,
                                )
                                content = f"Tool {block.name} errored: {e}"
                        else:
                            content = "Tool not available."
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                        })
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

        # Loop exhausted without a report
        raise RuntimeError(
            f"{self.name} agent exhausted {max_turns} turns without producing a report. "
            f"Last stop_reason: {getattr(last_response, 'stop_reason', '?')}"
        )

    # ─── Subclass hooks ──────────────────────────────────────────────

    async def _handle_action_tool(self, name: str, tool_input: dict) -> str:
        """Dispatch an action_tool call. Override in subclasses.

        Return a short confirmation string (the model sees it as the
        tool_result content). Raising is caught by the loop, which converts
        the exception into an error message the model can self-correct on.
        """
        return f"Tool {name} is registered but has no handler."

    # ─── Internals ───────────────────────────────────────────────────

    def _build_tools(self) -> list[dict]:
        tools: list[dict] = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": self.max_search_uses or settings.anthropic_max_search_uses,
            },
            {
                "name": self.report_tool_name,
                "description": self.report_tool_description,
                "input_schema": self.result_model.model_json_schema(),
            },
        ]
        for a in self.action_tools:
            tools.append({
                "name": a["name"],
                "description": a["description"],
                "input_schema": a["input_schema"],
            })
        return tools

    async def _call_api(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> anthropic.types.Message:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self.client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=settings.anthropic_max_tokens,
                    system=self.system_prompt,
                    messages=messages,
                    tools=tools,
                    timeout=settings.anthropic_timeout_seconds,
                )
            except anthropic.RateLimitError as e:
                last_error = e
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)
            except anthropic.APIConnectionError as e:
                last_error = e
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Connection error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, MAX_RETRIES, wait, e,
                )
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Server error %d (attempt %d/%d), retrying in %.1fs",
                        e.status_code, attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"Anthropic API call failed after {MAX_RETRIES} retries: {last_error}"
        ) from last_error
