"""Hermes policy helpers."""
from __future__ import annotations

from gods.config import runtime_config


def allow_agent_tool_provider(project_id: str) -> bool:
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return False
    return bool(getattr(proj, "hermes_allow_agent_tool_provider", False))
