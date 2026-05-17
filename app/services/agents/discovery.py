"""Sub-jurisdiction discovery agent.

For a country, finds states/provinces/cities/zones that levy their own
accommodation taxes. One run per country.
"""
from __future__ import annotations

from typing import ClassVar

from app.services.agents.base import BaseAnthropicAgent
from app.services.prompts.discovery import DISCOVERY_SYSTEM_PROMPT
from app.services.prompts.discovery_schema import AIDiscoveryResult


class DiscoveryAgent(BaseAnthropicAgent):
    name: ClassVar[str] = "discovery"
    system_prompt: ClassVar[str] = DISCOVERY_SYSTEM_PROMPT
    report_tool_name: ClassVar[str] = "report_discovery_findings"
    report_tool_description: ClassVar[str] = (
        "Report all discovered sub-jurisdictions that levy accommodation taxes. "
        "Call this tool exactly ONCE, only after you have finished researching. "
        "An empty jurisdictions list is a valid answer when nothing was found."
    )
    result_model: ClassVar[type] = AIDiscoveryResult
