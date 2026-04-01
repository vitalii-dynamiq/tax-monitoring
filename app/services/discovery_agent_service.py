from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import anthropic

from app.config import settings
from app.services.prompts.discovery_schema import AIDiscoveryResult

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

DISCOVERY_SYSTEM_PROMPT = """\
You are a tax jurisdiction research agent specializing in accommodation and tourism taxes.

## Your Task
For a given country, discover ALL sub-jurisdictions (states, provinces, cities, districts, \
special zones) that levy their OWN accommodation or tourism taxes. This means jurisdictions \
that have tax rules BEYOND what they inherit from their parent jurisdiction.

## What to Search For
- States/provinces that impose their own hotel/accommodation taxes
- Cities that levy their own city tax, tourist tax, bed tax, or accommodation surcharge
- Districts or special tourism zones with additional fees (e.g., resort areas, island zones)
- Any level of government that adds a tax layer to accommodation stays

## CRITICAL Rules
- ONLY include jurisdictions that have their OWN tax regulations. Do NOT include jurisdictions \
that only apply the parent's tax rates with no local additions.
- Every jurisdiction MUST include a concrete tax_summary describing what taxes it levies.
- Every jurisdiction MUST include a source_quote from an authoritative source.
- Use standard ISO-style codes: COUNTRY-STATE (e.g. AE-AJ), COUNTRY-STATE-CITY (e.g. US-NY-NYC).
- Set parent_code correctly: states/provinces have the country as parent, \
cities have the state as parent.
- If a country has a simple flat national tax with NO sub-jurisdiction variations, \
return an empty jurisdictions list and explain in the summary.

## Research Process
1. Search for "[country] accommodation tax jurisdictions", "[country] hotel tax by state/city"
2. Search for the country's official tax authority website
3. Identify all levels of government that levy accommodation taxes
4. For each level, enumerate the specific jurisdictions
5. Call report_discovery_findings with your complete findings

## When Done
After completing your research, call the report_discovery_findings tool. \
Do not end your turn without calling this tool.
"""


class JurisdictionDiscoveryAgent:
    """AI agent that discovers sub-jurisdictions with accommodation taxes for a country."""

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def discover_jurisdictions(
        self,
        country: Jurisdiction,
        existing_children: list[Jurisdiction],
    ) -> AIDiscoveryResult:
        """Run the agentic loop to discover sub-jurisdictions for a country."""
        existing_list = ""
        if existing_children:
            lines = [f"  - {j.code} ({j.name}, {j.jurisdiction_type})" for j in existing_children]
            existing_list = (
                f"\n\n## Already Known Sub-Jurisdictions ({len(existing_children)} total)\n"
                + "\n".join(lines)
                + "\n\nDiscover any ADDITIONAL jurisdictions not in this list."
            )

        user_prompt = (
            f"## Country to Analyze\n"
            f"- Code: {country.code}\n"
            f"- Name: {country.name}\n"
            f"- Currency: {country.currency_code}\n"
            f"- Timezone: {country.timezone or 'varies'}"
            f"{existing_list}\n\n"
            f"## Instructions\n"
            f"Research ALL sub-jurisdictions in {country.name} that levy their own "
            f"accommodation/tourism taxes. Search official government sources and "
            f"tax authority websites. Report findings using the report_discovery_findings tool."
        )

        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": settings.anthropic_max_search_uses,
            },
            {
                "name": "report_discovery_findings",
                "description": (
                    "Report all discovered sub-jurisdictions that levy accommodation taxes. "
                    "Call this ONLY after completing your research."
                ),
                "input_schema": AIDiscoveryResult.model_json_schema(),
            },
        ]

        messages: list[dict] = [{"role": "user", "content": user_prompt}]
        max_turns = settings.anthropic_max_agent_turns

        logger.info(
            "Starting jurisdiction discovery for %s (%s)",
            country.code,
            country.name,
        )

        for turn in range(max_turns):
            logger.info(
                "[%s] Discovery turn %d/%d — calling API",
                country.code, turn + 1, max_turns,
            )

            response = await self._call_api(messages, tools)

            tool_calls = [b.name for b in response.content if b.type == "tool_use"]
            logger.info(
                "[%s] Discovery turn %d: stop_reason=%s, tools=%s, tokens=%s/%s",
                country.code, turn + 1, response.stop_reason,
                tool_calls or "none",
                response.usage.input_tokens if response.usage else "?",
                response.usage.output_tokens if response.usage else "?",
            )

            # Check for our report tool
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_discovery_findings":
                    try:
                        result = AIDiscoveryResult.model_validate(block.input)
                    except Exception as e:
                        logger.error(
                            "Failed to parse discovery output for %s: %s",
                            country.code, e,
                        )
                        raise ValueError(f"AI returned invalid discovery output: {e}") from e

                    logger.info(
                        "Discovery complete for %s: %d jurisdictions found, depth=%d, confidence=%.2f",
                        country.code,
                        len(result.jurisdictions),
                        result.hierarchy_depth,
                        result.overall_confidence,
                    )
                    return result

            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "Please report your findings now by calling the "
                        "report_discovery_findings tool."
                    ),
                })
                continue

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                continue

        raise RuntimeError(
            f"Discovery agent exhausted {max_turns} turns for {country.code}"
        )

    async def _call_api(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> anthropic.types.Message:
        """Call Anthropic API with retry logic."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self.client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=settings.anthropic_max_tokens,
                    system=DISCOVERY_SYSTEM_PROMPT,
                    messages=messages,
                    tools=tools,
                    timeout=settings.anthropic_timeout_seconds,
                )
            except anthropic.RateLimitError as e:
                last_error = e
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            except anthropic.APIConnectionError as e:
                last_error = e
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                else:
                    raise
        raise RuntimeError(f"Anthropic API failed after {MAX_RETRIES} retries: {last_error}") from last_error
