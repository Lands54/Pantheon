"""Agent runtime policy resolver (agent override > project default)."""
from __future__ import annotations

from typing import Any

from gods.config import runtime_config

PHASE_STRATEGY_STRICT_TRIAD = "strict_triad"
PHASE_STRATEGY_ITERATIVE_ACTION = "iterative_action"
PHASE_STRATEGIES = {PHASE_STRATEGY_STRICT_TRIAD, PHASE_STRATEGY_ITERATIVE_ACTION}


def _project(project_id: str):
    return runtime_config.projects.get(project_id)


def _agent_settings(project_id: str, agent_id: str) -> dict[str, Any]:
    proj = _project(project_id)
    if not proj:
        return {}
    settings = getattr(proj, "agent_settings", {}) or {}
    row = settings.get(agent_id)
    if not row:
        return {}
    if hasattr(row, "model_dump"):
        return row.model_dump()
    if isinstance(row, dict):
        return row
    return {}


def resolve_phase_mode_enabled(project_id: str, agent_id: str) -> bool:
    settings = _agent_settings(project_id, agent_id)
    if settings.get("phase_mode_enabled") is not None:
        return bool(settings.get("phase_mode_enabled"))
    proj = _project(project_id)
    return bool(getattr(proj, "phase_mode_enabled", True) if proj else True)


def resolve_phase_strategy(project_id: str, agent_id: str) -> str:
    settings = _agent_settings(project_id, agent_id)
    agent_value = settings.get("phase_strategy")
    if isinstance(agent_value, str) and agent_value:
        if agent_value == "freeform":
            return "freeform"
        if agent_value in PHASE_STRATEGIES:
            return agent_value
        return PHASE_STRATEGY_STRICT_TRIAD

    proj = _project(project_id)
    value = str(getattr(proj, "phase_strategy", PHASE_STRATEGY_STRICT_TRIAD) if proj else PHASE_STRATEGY_STRICT_TRIAD)
    if value == "freeform":
        return "freeform"
    if value in PHASE_STRATEGIES:
        return value
    return PHASE_STRATEGY_STRICT_TRIAD
