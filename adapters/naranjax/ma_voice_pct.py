"""Compatibility alias: the generic adapter now lives in etl_core (ADR-001, decision 2)."""

from etl_core.contracts import SubprocessAdapter

MaVoicePctAdapter = SubprocessAdapter

__all__ = ["MaVoicePctAdapter"]
