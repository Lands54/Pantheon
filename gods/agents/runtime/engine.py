"""Unified agent runtime entry powered by LangGraph."""
from __future__ import annotations

from gods.agents.runtime.models import RuntimeState
from gods.agents.runtime.nodes import on_runtime_error
from gods.agents.runtime.registry import get_strategy_builder, register_strategy
from gods.agents.runtime.strategies.freeform import build_freeform_graph
from gods.agents.runtime.strategies.react_graph import build_react_graph
from gods.agents.runtime_policy import resolve_phase_strategy
from gods.config import runtime_config
from gods.mnemosyne.intent_builders import intent_from_agent_marker


_REGISTERED = False


def _register_defaults() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    register_strategy("react_graph", build_react_graph)
    register_strategy("freeform", build_freeform_graph)
    _REGISTERED = True


def _max_rounds(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
    return max(1, min(value, 64))


def run_agent_runtime(agent, state: RuntimeState):
    _register_defaults()
    strategy = resolve_phase_strategy(agent.project_id, agent.agent_id)
    state["strategy"] = strategy
    state["agent_id"] = agent.agent_id
    state["project_id"] = agent.project_id
    state.setdefault("messages", [])
    state.setdefault("next_step", "")
    state["loop_count"] = int(state.get("loop_count", 0) or 0)
    state["max_rounds"] = _max_rounds(agent.project_id)
    state["pulse_meta"] = dict(state.get("__pulse_meta", {}) or {})

    if strategy == "freeform":
        agent._record_intent(
            intent_from_agent_marker(
                project_id=agent.project_id,
                agent_id=agent.agent_id,
                marker="freeform_mode",
                payload={"project_id": agent.project_id, "agent_id": agent.agent_id},
            )
        )

    builder = get_strategy_builder(strategy)
    graph = builder(agent)
    try:
        out = graph.invoke(state)
        if isinstance(out, dict):
            state.update(out)
        if "finalize_control" in state:
            state["__finalize_control"] = state.get("finalize_control")
        return state
    except Exception as e:
        return on_runtime_error(agent, state, e)
