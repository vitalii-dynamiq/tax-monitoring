"""Country-scoped tax monitoring agent.

Runs an agentic loop with web_search over the entire country (including all
sub-jurisdictions) and reports rate/rule changes via the report_tax_findings
tool. One run per country.
"""
from __future__ import annotations

from typing import ClassVar

from app.services.agents.base import BaseAnthropicAgent
from app.services.prompts.output_schema import AIMonitoringResult
from app.services.prompts.tax_monitoring import SYSTEM_PROMPT


class TaxMonitoringAgent(BaseAnthropicAgent):
    name: ClassVar[str] = "tax_monitoring"
    system_prompt: ClassVar[str] = SYSTEM_PROMPT
    report_tool_name: ClassVar[str] = "report_tax_findings"
    report_tool_description: ClassVar[str] = (
        "Report the complete tax regulation findings for this country and all its "
        "sub-jurisdictions. Call this tool exactly ONCE, only after you have "
        "finished all your research. Include ALL rates and rules found, each "
        "tagged with the jurisdiction_code it applies to."
    )
    result_model: ClassVar[type] = AIMonitoringResult
