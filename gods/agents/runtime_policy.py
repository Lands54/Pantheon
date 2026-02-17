"""Agent runtime strategy resolver (agent override > project default)."""
from __future__ import annotations

from typing import Any

from gods.config import runtime_config

PHASE_STRATEGY_REACT_GRAPH = "react_graph"
PHASE_STRATEGY_FREEFORM = "freeform"
PHASE_STRATEGIES = {PHASE_STRATEGY_REACT_GRAPH, PHASE_STRATEGY_FREEFORM}


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


def _validate_strategy(raw: str, source: str) -> str:
    value = str(raw or "").strip().lower()
    if value in PHASE_STRATEGIES:
        return value
    raise ValueError(f"invalid phase_strategy '{raw}' from {source}; allowed: react_graph|freeform")


def resolve_phase_strategy(project_id: str, agent_id: str) -> str:
    settings = _agent_settings(project_id, agent_id)
    agent_value = settings.get("phase_strategy")
    if isinstance(agent_value, str) and agent_value:
        return _validate_strategy(agent_value, f"agent:{project_id}/{agent_id}")

    proj = _project(project_id)
    value = getattr(proj, "phase_strategy", PHASE_STRATEGY_REACT_GRAPH) if proj else PHASE_STRATEGY_REACT_GRAPH
    return _validate_strategy(str(value), f"project:{project_id}")
