"""Agent registry — one place to find/add/swap agents.

Adding a new agent is two steps:
  1. Create app/services/agents/<your_agent>.py extending BaseAnthropicAgent
     (or any class that exposes async .run(user_prompt=..., recorder=...))
  2. Add it to AGENTS below.

Swapping an Anthropic agent for an external runner (OpenAI, in-house service)
later is the same two steps, since the registry doesn't depend on the parent
class.
"""
from __future__ import annotations

from typing import Any

from app.services.agents.base import BaseAnthropicAgent
from app.services.agents.discovery import DiscoveryAgent
from app.services.agents.tax_monitoring import TaxMonitoringAgent
from app.services.agents.triage import TriageAgent

AGENTS: dict[str, type[Any]] = {
    TaxMonitoringAgent.name: TaxMonitoringAgent,
    DiscoveryAgent.name: DiscoveryAgent,
    TriageAgent.name: TriageAgent,
}


def get_agent(name: str) -> Any:
    """Instantiate an agent by name. Raises KeyError if unknown."""
    try:
        cls = AGENTS[name]
    except KeyError as e:
        raise KeyError(
            f"Unknown agent: {name!r}. Registered: {sorted(AGENTS)}"
        ) from e
    return cls()


__all__ = [
    "AGENTS",
    "BaseAnthropicAgent",
    "DiscoveryAgent",
    "TaxMonitoringAgent",
    "TriageAgent",
    "get_agent",
]
