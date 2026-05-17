"""Backwards-compatibility shim.

The real implementation lives in app/services/agents/tax_monitoring.py.
This module re-exports the class so existing imports continue to work.
"""
from app.services.agents.tax_monitoring import TaxMonitoringAgent

__all__ = ["TaxMonitoringAgent"]
