"""Chaos snapshot builder for strategy material aggregation."""
from __future__ import annotations

import time
from typing import Any

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.chaos.contracts import ResourceSnapshot, MemoryMaterials
from gods.config import runtime_config
from gods.hermes import facade as hermes_facade
from gods.mnemosyne.facade import (
    latest_intent_seq,
    read_profile,
    read_task_state,
)
from gods.tools import available_tool_names


def _render_task_state(task_state: dict[str, Any]) -> str:
    lines = [f"Objective: {str(task_state.get('objective', '') or '')}"]
    plan = list(task_state.get("plan", []) or [])
    progress = list(task_state.get("progress", []) or [])
    blockers = list(task_state.get("blockers", []) or [])
    next_actions = list(task_state.get("next_actions", []) or [])
    if plan:
        lines.append("Plan:")
        lines.extend([f"- {x}" for x in plan[:10]])
    if progress:
        lines.append("Progress:")
        lines.extend([f"- {x}" for x in progress[:12]])
    if blockers:
        lines.append("Blockers:")
        lines.extend([f"- {x}" for x in blockers[:8]])
    if next_actions:
        lines.append("Next Actions:")
        lines.extend([f"- {x}" for x in next_actions[:8]])
    return "\n".join(lines)


def build_memory_materials(agent, state: dict[str, Any], *, strategy: str) -> MemoryMaterials:
    project_id = agent.project_id
    agent_id = agent.agent_id
    objective_fallback = str(state.get("context", "") or "")
    task_state = dict(read_task_state(project_id, agent_id, objective_fallback=objective_fallback) or {})
    profile = str(read_profile(project_id, agent_id) or "")
    
    directives = ""
    try:
        directives = str(agent._build_behavior_directives() or "")
    except Exception:
        pass
    tools_desc = ""
    try:
        tools_desc = str(agent._render_tools_desc("llm_think") or "")
    except Exception:
        pass
    return MemoryMaterials(
        profile=f"{profile}\nProject: {project_id}".strip(),
        directives=directives,
        task_state=_render_task_state(task_state),
        tools=tools_desc,
        inbox_hint=str(agent._build_inbox_context_hint() or ""),
    )


def _mailbox_summary(state: dict[str, Any]) -> dict[str, Any]:
    intents = list(state.get("mailbox", []) or [])
    inbox_count = 0
    outbox_count = 0
    for item in intents:
        key = str(getattr(item, "intent_key", "") or "")
        if key.startswith("inbox."):
            inbox_count += 1
        if key.startswith("outbox."):
            outbox_count += 1
    return {
        "intents": intents,
        "inbox_count": inbox_count,
        "outbox_count": outbox_count,
        "delivered_ids": list(state.get("__inbox_delivered_ids", []) or []),
    }


def _event_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(state.get("triggers", []) or []):
        rows.append(
            {
                "intent_key": str(getattr(item, "intent_key", "") or ""),
                "source_kind": str(getattr(item, "source_kind", "") or ""),
                "payload": dict(getattr(item, "payload", {}) or {}),
            }
        )
    return rows


def _contracts_summary(project_id: str) -> dict[str, Any]:
    try:
        contracts = hermes_facade.list_contracts(project_id, include_disabled=True)
    except Exception:
        contracts = []
    try:
        protocols = hermes_facade.list_protocols(project_id)
    except Exception:
        protocols = []
    try:
        port_leases = hermes_facade.list_ports(project_id)
    except Exception:
        port_leases = []
    return {
        "contracts_count": len(contracts if isinstance(contracts, list) else []),
        "protocols_count": len(protocols if isinstance(protocols, list) else []),
        "port_leases_count": len(port_leases if isinstance(port_leases, list) else []),
    }


def _config_view(project_id: str, agent_id: str) -> dict[str, Any]:
    proj = runtime_config.projects.get(project_id)
    agent_cfg = getattr(proj, "agent_settings", {}).get(agent_id) if proj else None
    return {
        "project_id": project_id,
        "agent_id": agent_id,
        "phase_strategy": resolve_phase_strategy(project_id, agent_id),
        "project": proj.model_dump() if hasattr(proj, "model_dump") else {},
        "agent": agent_cfg.model_dump() if hasattr(agent_cfg, "model_dump") else {},
    }


def _context_materials(agent, state: dict[str, Any], *, strategy: str) -> MemoryMaterials:
    return build_memory_materials(agent, state, strategy=strategy)


def build_resource_snapshot(agent, state: dict[str, Any], strategy: str | None = None) -> ResourceSnapshot:
    # Always pull incremental materials before snapshotting to ensure SSOT sync
    pull_incremental_materials(agent, state)
    
    sid = str(strategy or state.get("strategy") or resolve_phase_strategy(agent.project_id, agent.agent_id))
    pulse_meta = dict(state.get("__pulse_meta", {}) or {})
    mailbox = _mailbox_summary(state)
    events = _event_rows(state)
    memory = {
        "triggers_count": len(events),
        "mailbox_intents_count": len(list(state.get("mailbox", []) or [])),
        "messages_in_state_count": len(list(state.get("messages", []) or [])),
    }
    return ResourceSnapshot(
        project_id=agent.project_id,
        agent_id=agent.agent_id,
        strategy=sid,
        events=events,
        mailbox=mailbox,
        memory=memory,
        contracts=_contracts_summary(agent.project_id),
        tool_catalog=available_tool_names(),
        config_view=_config_view(agent.project_id, agent.agent_id),
        context_materials=build_memory_materials(agent, state, strategy=sid),
        runtime_meta={
            "pulse_meta": pulse_meta,
            "intent_seq_latest": int(latest_intent_seq(agent.project_id, agent.agent_id)),
            "created_at": time.time(),
        },
    )


def pull_incremental_materials(
    agent,
    state: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """SequentialV1 now consumes PulseLedger directly; no card sync in Chaos."""
    project_id = agent.project_id
    agent_id = agent.agent_id

    last_synced_seq = int(state.get("__chaos_synced_seq", 0) or 0)
    current_latest_seq = int(latest_intent_seq(project_id, agent_id))
    state["__chaos_synced_seq"] = current_latest_seq

    return {
        "runtime_meta": {
            "incremental_pull": {
                "new_trigger_count": 0,
                "new_mailbox_count": 0,
                "last_synced_seq": last_synced_seq,
                "current_latest_seq": current_latest_seq,
            }
        }
    }
