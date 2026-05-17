"""Backwards-compatibility shim.

The real implementation lives in app/services/agents/discovery.py.
The discovery system prompt lives in app/services/prompts/discovery.py.
"""
from app.services.agents.discovery import DiscoveryAgent
from app.services.prompts.discovery import DISCOVERY_SYSTEM_PROMPT

# Keep alias for legacy imports
JurisdictionDiscoveryAgent = DiscoveryAgent

__all__ = ["DISCOVERY_SYSTEM_PROMPT", "DiscoveryAgent", "JurisdictionDiscoveryAgent"]
