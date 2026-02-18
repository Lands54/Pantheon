"""Unified agent runtime entry powered by LangGraph."""
from __future__ import annotations

from gods.agents.runtime.models import RuntimeState
from gods.config import runtime_config
from gods.metis.strategy_runtime import run_metis_strategy


def _max_rounds(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
    return max(1, min(value, 64))


def run_agent_runtime(agent, state: RuntimeState):
    state["agent_id"] = agent.agent_id
    state["project_id"] = agent.project_id
    state.setdefault("messages", [])
    state.setdefault("next_step", "")
    state["loop_count"] = int(state.get("loop_count", 0) or 0)
    state["max_rounds"] = _max_rounds(agent.project_id)
    state["pulse_meta"] = dict(state.get("__pulse_meta", {}) or {})
    out = run_metis_strategy(agent, state)
    if "finalize_control" in out:
        out["__finalize_control"] = out.get("finalize_control")
    return out
