"""Chaos snapshot builder for strategy material aggregation."""
from __future__ import annotations

import time
from typing import Any

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.chaos.contracts import ResourceSnapshot
from gods.config import runtime_config
from gods.hermes import facade as hermes_facade
from gods.iris.facade import fetch_mailbox_intents, has_pending
from gods.mnemosyne.facade import (
    intent_from_angelia_event,
    load_chronicle_for_context,
    load_state_window,
    read_profile,
    read_task_state,
    list_observations,
    render_intents_for_llm,
)
from gods.tools import available_tool_names
from types import SimpleNamespace


def _render_mailbox_with_attachment_hints(intents: list[Any]) -> list[str]:
    lines = list(render_intents_for_llm(intents))
    for intent in list(intents or []):
        payload = dict(getattr(intent, "payload", {}) or {})
        attachment_ids = [str(x).strip() for x in list(payload.get("attachments", []) or []) if str(x).strip()]
        if attachment_ids:
            lines.append(
                f"[MAILBOX_ATTACHMENTS] message_id={str(payload.get('message_id',''))} "
                f"attachments={len(attachment_ids)} ids={','.join(attachment_ids[:5])}"
            )
    return lines


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


def _context_materials(agent, state: dict[str, Any]) -> dict[str, Any]:
    project_id = agent.project_id
    agent_id = agent.agent_id
    triggers = list(state.get("triggers", []) or [])
    mailbox = list(state.get("mailbox", []) or [])
    objective_fallback = str(state.get("context", "") or "")
    task_state = dict(read_task_state(project_id, agent_id, objective_fallback=objective_fallback) or {})
    return {
        "profile": read_profile(project_id, agent_id),
        "chronicle": load_chronicle_for_context(project_id, agent_id, fallback=""),
        "task_state": {
            "objective": str(task_state.get("objective", "")),
            "plan": list(task_state.get("plan", []) or []),
            "progress": list(task_state.get("progress", []) or []),
            "blockers": list(task_state.get("blockers", []) or []),
            "next_actions": list(task_state.get("next_actions", []) or []),
        },
        "observations": list_observations(project_id, agent_id, limit=200),
        "triggers_rendered": render_intents_for_llm(triggers),
        "mailbox_rendered": _render_mailbox_with_attachment_hints(mailbox),
        "state_window_messages": list(state.get("messages", []) or []),
    }


def build_resource_snapshot(agent, state: dict[str, Any], strategy: str | None = None) -> ResourceSnapshot:
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
        state_window=load_state_window(agent.project_id, agent.agent_id),
        tool_catalog=available_tool_names(),
        config_view=_config_view(agent.project_id, agent.agent_id),
        context_materials=_context_materials(agent, state),
        runtime_meta={
            "pulse_meta": pulse_meta,
            "created_at": time.time(),
        },
    )


def pull_incremental_materials(
    agent,
    state: dict[str, Any],
    *,
    event_limit: int = 50,
    mailbox_budget: int = 3,
) -> dict[str, Any]:
    """Incrementally pull worker-claimed events and Iris mailbox updates into runtime state."""
    project_id = agent.project_id
    agent_id = agent.agent_id

    state.setdefault("triggers", [])
    state.setdefault("mailbox", [])

    seen_event_ids = set(str(x) for x in list(state.get("__chaos_seen_event_ids", []) or []))
    seen_mailbox_fp = set(str(x) for x in list(state.get("__chaos_seen_mailbox_fp", []) or []))

    new_trigger_count = 0
    new_mailbox_count = 0

    claim_fn = state.get("__worker_claim_events")
    rows: list[dict[str, Any]] = []
    if callable(claim_fn):
        try:
            raw = claim_fn(max(1, min(int(event_limit or 50), 200)))
            if isinstance(raw, list):
                rows = [x for x in raw if isinstance(x, dict)]
        except Exception:
            rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("event_id", "") or "")
        if not eid or eid in seen_event_ids:
            continue
        intent = intent_from_angelia_event(SimpleNamespace(**row), stage="trigger")
        state["triggers"].append(intent)
        seen_event_ids.add(eid)
        new_trigger_count += 1

    if has_pending(project_id, agent_id):
        intents = fetch_mailbox_intents(project_id, agent_id, max(1, int(mailbox_budget or 3)))
        for intent in intents:
            key = str(getattr(intent, "intent_key", "") or "")
            payload = dict(getattr(intent, "payload", {}) or {})
            fp = f"{key}|{payload.get('message_id','')}|{payload.get('event_ids','')}|{payload.get('count','')}"
            if fp in seen_mailbox_fp:
                continue
            state["mailbox"].append(intent)
            seen_mailbox_fp.add(fp)
            new_mailbox_count += 1

    state["__chaos_seen_event_ids"] = list(seen_event_ids)
    state["__chaos_seen_mailbox_fp"] = list(seen_mailbox_fp)

    return {
        "runtime_meta": {
            "incremental_pull": {
                "new_trigger_count": int(new_trigger_count),
                "new_mailbox_count": int(new_mailbox_count),
                "event_limit": int(event_limit),
                "mailbox_budget": int(mailbox_budget),
            }
        }
    }
