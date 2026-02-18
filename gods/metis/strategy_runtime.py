"""Metis strategy runtime orchestration."""
from __future__ import annotations

from gods.agents.runtime.nodes import on_runtime_error
from gods.agents.runtime_policy import resolve_phase_strategy
from gods.metis.registry import get_strategy_builder, register_strategy, list_strategies
from gods.agents.runtime.strategies.freeform import build_freeform_graph
from gods.agents.runtime.strategies.react_graph import build_react_graph
from gods.metis.snapshot import build_runtime_envelope, resolve_refresh_mode
from gods.mnemosyne.intent_builders import intent_from_agent_marker


_REGISTERED = False


def _register_defaults() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    register_strategy("react_graph", build_react_graph)
    register_strategy("freeform", build_freeform_graph)
    _REGISTERED = True


def validate_spec_registry_alignment(spec_strategy_ids: list[str]) -> list[str]:
    _register_defaults()
    reg = set(list_strategies())
    spec = {str(x).strip().lower() for x in list(spec_strategy_ids or []) if str(x).strip()}
    return sorted((reg - spec) | (spec - reg))


def run_metis_strategy(agent, state: dict):
    _register_defaults()
    strategy = resolve_phase_strategy(agent.project_id, agent.agent_id)
    state["strategy"] = strategy
    refresh_mode = resolve_refresh_mode(state if isinstance(state, dict) else {})
    envelope = build_runtime_envelope(agent, state, strategy=strategy)
    envelope.policy = dict(envelope.policy or {})
    envelope.policy["refresh_mode"] = refresh_mode
    state["__metis_envelope"] = envelope

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
        return state
    except Exception as e:
        return on_runtime_error(agent, state, e)

