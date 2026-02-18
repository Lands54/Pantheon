"""Metis envelope builder that consumes Chaos resource snapshots."""
from __future__ import annotations

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.chaos.snapshot import build_resource_snapshot, pull_incremental_materials
from gods.config import runtime_config
from gods.metis.contracts import ResourceSnapshot, RuntimeEnvelope
from gods.metis.strategy_specs import get_strategy_spec


def resolve_refresh_mode(state: dict) -> str:
    st = dict(state or {})
    project_id = str(st.get("project_id", "") or "")
    agent_id = str(st.get("agent_id", "") or "")
    proj = runtime_config.projects.get(project_id) if project_id else None
    mode = ""
    if proj and agent_id:
        agent_cfg = getattr(proj, "agent_settings", {}).get(agent_id)
        if agent_cfg:
            mode = str(getattr(agent_cfg, "metis_refresh_mode", "") or "").strip().lower()
    if not mode and proj:
        mode = str(getattr(proj, "metis_refresh_mode", "pulse") or "pulse").strip().lower()
    if not mode:
        mode = str(st.get("__metis_refresh_mode", "pulse") or "pulse").strip().lower()
    return "node" if mode == "node" else "pulse"


def build_runtime_envelope(agent, state: dict, strategy: str | None = None) -> RuntimeEnvelope:
    sid = str(strategy or state.get("strategy") or resolve_phase_strategy(agent.project_id, agent.agent_id))
    spec = get_strategy_spec(sid)
    snapshot = build_resource_snapshot(agent, state, strategy=sid)
    return RuntimeEnvelope(
        strategy=sid,
        state=state,
        resource_snapshot=snapshot,
        policy={
            "required_resources": list(spec.required_resources),
            "phases": list(spec.phases),
            "default_tool_policies": {k: list(v) for k, v in spec.default_tool_policies.items()},
            "node_order": list(spec.node_order),
        },
        trace={"provider": "gods.metis.snapshot", "strategy_spec": spec.strategy_id},
    )


def refresh_runtime_envelope(
    agent,
    state: dict,
    *,
    strategy: str | None = None,
    reason: str = "",
    snapshot_patch: dict | None = None,
) -> RuntimeEnvelope:
    mode = resolve_refresh_mode(state if isinstance(state, dict) else {})
    seq = int((state or {}).get("__metis_refresh_seq", 0) or 0) + 1
    state["__metis_refresh_seq"] = seq
    incremental_patch: dict | None = None
    if mode == "node":
        incremental_patch = pull_incremental_materials(agent, state)
    envelope = build_runtime_envelope(agent, state, strategy=strategy)
    if isinstance(incremental_patch, dict) and incremental_patch:
        envelope.resource_snapshot = envelope.resource_snapshot.update(**incremental_patch)
    if isinstance(snapshot_patch, dict) and snapshot_patch:
        envelope.resource_snapshot = envelope.resource_snapshot.update(**snapshot_patch)
    trace = dict(envelope.trace or {})
    trace.update({"refresh_seq": seq, "refresh_reason": str(reason or "")})
    envelope.trace = trace
    state["__metis_envelope"] = envelope
    return envelope


def build_resource_snapshot_via_chaos(agent, state: dict, strategy: str | None = None) -> ResourceSnapshot:
    return build_resource_snapshot(agent, state, strategy=strategy)
