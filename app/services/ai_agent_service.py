from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import anthropic

from app.config import settings
from app.services.prompts.output_schema import AIMonitoringResult
from app.services.prompts.tax_monitoring import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction
    from app.models.tax_rate import TaxRate
    from app.models.tax_rule import TaxRule

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


class TaxMonitoringAgent:
    """Agentic tax monitoring using Anthropic Claude with web search.

    Uses an agentic loop: Claude autonomously searches the web for current
    tax regulations, analyzes findings, and reports structured results.
    """

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. "
                "Set it in .env or environment variables."
            )
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def research_jurisdiction(
        self,
        jurisdiction: Jurisdiction,
        current_rates: list[TaxRate],
        current_rules: list[TaxRule],
        monitored_urls: list[str],
    ) -> AIMonitoringResult:
        """Run the agentic loop to research tax regulations for a jurisdiction.

        Claude uses web_search to find current tax info, then reports findings
        via the report_tax_findings tool (structured output).
        """
        user_prompt = build_user_prompt(
            jurisdiction, current_rates, current_rules, monitored_urls
        )

        tools = [
            # Anthropic's built-in web search (server tool)
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": settings.anthropic_max_search_uses,
            },
            # Our custom tool for structured output
            {
                "name": "report_tax_findings",
                "description": (
                    "Report the complete tax regulation findings for this jurisdiction. "
                    "Call this tool ONLY after you have finished all your research. "
                    "Include ALL rates and rules found, with change types and evidence."
                ),
                "input_schema": AIMonitoringResult.model_json_schema(),
            },
        ]

        messages: list[dict] = [{"role": "user", "content": user_prompt}]
        max_turns = settings.anthropic_max_agent_turns

        logger.info(
            "Starting agentic research for %s (model=%s, max_turns=%d, max_searches=%d)",
            jurisdiction.code,
            settings.anthropic_model,
            max_turns,
            settings.anthropic_max_search_uses,
        )

        for turn in range(max_turns):
            logger.info(
                "[%s] Turn %d/%d — calling API (stop_reason will determine next action)",
                jurisdiction.code, turn + 1, max_turns,
            )

            response = await self._call_api(messages, tools)

            # Log what happened in this turn
            tool_calls = [b.name for b in response.content if b.type == "tool_use"]
            _ = [b for b in response.content if hasattr(b, "text")]  # noqa: F841
            logger.info(
                "[%s] Turn %d response: stop_reason=%s, tools_called=%s, "
                "input_tokens=%s, output_tokens=%s",
                jurisdiction.code, turn + 1, response.stop_reason,
                tool_calls or "none",
                response.usage.input_tokens if response.usage else "?",
                response.usage.output_tokens if response.usage else "?",
            )

            # Check if Claude called our report tool — means research is done
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_tax_findings":
                    try:
                        result = AIMonitoringResult.model_validate(block.input)
                    except Exception as e:
                        logger.error(
                            "Failed to parse report_tax_findings output for %s: %s\nRaw input: %s",
                            jurisdiction.code,
                            e,
                            block.input,
                        )
                        raise ValueError(
                            f"AI returned invalid structured output: {e}"
                        ) from e

                    logger.info(
                        "AI research complete for %s after %d turns: "
                        "%d rates, %d rules, confidence=%.2f",
                        jurisdiction.code,
                        turn + 1,
                        len(result.rates),
                        len(result.rules),
                        result.overall_confidence,
                    )
                    return result

            # If end_turn with no tool calls, nudge the agent to report
            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "You have finished your research. Now please report your findings "
                        "by calling the report_tax_findings tool with all the tax rates "
                        "and rules you found."
                    ),
                })
                continue

            # tool_use (web_search or other) — add response to conversation and continue
            # For server tools like web_search, the API handles execution.
            # We just need to add the assistant response so the loop continues.
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                # For server tools, results are automatically included in the next turn.
                # For any user-defined tool calls that aren't report_tax_findings,
                # we need to provide results. But web_search is server-side.
                # Check if there are any non-server tool calls that need results:
                tool_results = []
                for block in response.content:
                    if (
                        block.type == "tool_use"
                        and block.name != "report_tax_findings"
                        and block.name != "web_search"
                    ):
                        # Unexpected tool call — return empty result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Tool not available.",
                        })

                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

        # Exhausted all turns without getting a report
        raise RuntimeError(
            f"AI agent exhausted {max_turns} turns for {jurisdiction.code} "
            f"without producing a report. Last stop_reason: {response.stop_reason}"
        )

    async def _call_api(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> anthropic.types.Message:
        """Call the Anthropic API with retry logic for transient failures."""
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                return await self.client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=settings.anthropic_max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=tools,
                    timeout=settings.anthropic_timeout_seconds,
                )
            except anthropic.RateLimitError as e:
                last_error = e
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Rate limited by Anthropic API (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
            except anthropic.APIConnectionError as e:
                last_error = e
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Connection error to Anthropic API (attempt %d/%d): %s, retrying in %.1fs",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                # 5xx errors are retryable, 4xx are not
                if e.status_code >= 500:
                    last_error = e
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Anthropic API server error %d (attempt %d/%d), retrying in %.1fs",
                        e.status_code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"Anthropic API call failed after {MAX_RETRIES} retries: {last_error}"
        ) from last_error
