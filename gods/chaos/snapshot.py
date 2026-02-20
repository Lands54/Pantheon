"""Chaos snapshot builder for strategy material aggregation."""
from __future__ import annotations

import hashlib
import time
from types import SimpleNamespace
from typing import Any

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.chaos.contracts import ResourceSnapshot, MemoryMaterials
from gods.config import runtime_config
from gods.hermes import facade as hermes_facade
from gods.iris.facade import get_mailbox_glance
from gods.mnemosyne import record_intent
from gods.mnemosyne.facade import (
    fetch_intents_between,
    intent_from_angelia_event,
    latest_intent_seq,
    read_profile,
    read_task_state,
    validate_card_buckets,
)
from gods.tools import available_tool_names


def _mailbox_card_id(intent: Any, index: int) -> str:
    payload = dict(getattr(intent, "payload", {}) or {})
    intent_key = str(getattr(intent, "intent_key", "") or "").strip() or "mailbox.unknown"
    message_id = str(payload.get("message_id", "") or "").strip()
    if message_id:
        return f"material.mailbox:{message_id}"
    title = str(payload.get("title", "") or "")
    sender = str(payload.get("sender", "") or payload.get("to_agent_id", "") or "")
    fp = hashlib.sha1(f"{intent_key}|{title}|{sender}|{index}".encode("utf-8")).hexdigest()[:10]
    return f"material.mailbox:{fp}"


def _mailbox_source_intent_ids(intent: Any) -> list[str]:
    iid = str(getattr(intent, "intent_id", "") or "").strip()
    return [iid] if iid else []


def _render_single_mail(intent: Any) -> str:
    key = str(getattr(intent, "intent_key", "") or "").strip()
    payload = dict(getattr(intent, "payload", {}) or {})
    title = str(payload.get("title", "") or "")
    sender = str(payload.get("sender", "") or payload.get("to_agent_id", "") or "")
    mid = str(payload.get("message_id", "") or "")
    lines: list[str] = [f"[MAIL] key={key} title={title} sender={sender} mid={mid}"]
    attachment_ids = [str(x).strip() for x in list(payload.get("attachments", []) or []) if str(x).strip()]
    if attachment_ids:
        lines.append(
            f"[MAILBOX_ATTACHMENTS] message_id={mid} attachments={len(attachment_ids)} ids={','.join(attachment_ids[:5])}"
        )
    return "\n".join(lines)


def _render_triggers(triggers: list[Any]) -> str:
    lines = [f"- {str(getattr(x, 'fallback_text', '') or '').strip()}" for x in list(triggers or []) if str(getattr(x, 'fallback_text', '') or '').strip()]
    return "\n".join(lines) if lines else "(no specific trigger events)"


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


def _card(*, card_id: str, kind: str, text: str, source_seq: int, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    md = {"read_only": True, "declared_material": True}
    md.update(dict(meta or {}))
    return {
        "card_id": str(card_id),
        "kind": str(kind),
        "text": str(text or "").strip(),
        "source_intent_ids": [],
        "source_intent_seq_max": int(source_seq),
        "derived_from_card_ids": [],
        "supersedes_card_ids": [],
        "compression_type": "",
        "meta": md,
        "created_at": time.time(),
    }


def _state_cards_for_bucket(state: dict[str, Any], bucket: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list(state.get("cards", []) or []):
        if not isinstance(row, dict):
            continue
        meta = dict(row.get("meta", {}) or {})
        if str(meta.get("bucket", "") or "").strip() != str(bucket):
            continue
        out.append(dict(row))
    return out


def build_memory_materials(agent, state: dict[str, Any], *, strategy: str) -> MemoryMaterials:
    project_id = agent.project_id
    agent_id = agent.agent_id
    objective_fallback = str(state.get("context", "") or "")
    task_state = dict(read_task_state(project_id, agent_id, objective_fallback=objective_fallback) or {})
    profile = str(read_profile(project_id, agent_id) or "")
    
    # Base cards that are always present (virtual intents)
    flat_cards: list[dict[str, Any]] = []

    # Profile
    flat_cards.append(_card(
        card_id="material.profile",
        kind="task",
        text=f"[PROFILE]\n{profile}\nProject: {project_id}",
        source_seq=-1,
        meta={"source_kind": "agent", "intent_key": "material.profile"}
    ))

    # Task State
    flat_cards.append(_card(
        card_id="material.task_state",
        kind="task",
        text=f"[TASK_STATE]\n{_render_task_state(task_state)}",
        source_seq=-1,
        meta={"source_kind": "agent", "intent_key": "material.task_state"}
    ))

    # Real Context Cards from Mnemosyne (the 'to_llm_context' items)
    for row in list(state.get("cards", []) or []):
        if isinstance(row, dict):
            # Ensure source_kind is correctly mapped in meta if missing
            m = dict(row.get("meta", {}) or {})
            if "source_kind" not in m:
                ik = str(m.get("intent_key", "") or "")
                # We could look up semantics_service here, but usually it's already in row
            flat_cards.append(dict(row))

    # Policy / Directives
    directives = ""
    try:
        directives = str(agent._build_behavior_directives() or "")
    except Exception:
        pass
    if directives:
        flat_cards.append(_card(
            card_id="material.directives",
            kind="policy",
            text=f"[DIRECTIVES]\n{directives}",
            source_seq=-1,
            meta={"source_kind": "agent", "intent_key": "material.directives"}
        ))

    # Tools
    tools_desc = ""
    try:
        tools_desc = str(agent._render_tools_desc("llm_think") or "")
    except Exception:
        pass
    if tools_desc:
        flat_cards.append(_card(
            card_id="material.tools",
            kind="policy",
            text=f"[TOOLS]\n{tools_desc}",
            source_seq=-1,
            meta={"source_kind": "agent", "intent_key": "material.tools"}
        ))

    return MemoryMaterials(cards=flat_cards)


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
    """Incrementally pull new intents into runtime state using Chaos Sync."""
    project_id = agent.project_id
    agent_id = agent.agent_id

    # Sync using sequence cursor
    last_synced_seq = int(state.get("__chaos_synced_seq", 0) or 0)
    current_latest_seq = int(latest_intent_seq(project_id, agent_id))

    state.setdefault("triggers", [])
    state.setdefault("mailbox", [])
    state.setdefault("cards", [])

    new_trigger_count = 0
    new_mailbox_count = 0

    if last_synced_seq < current_latest_seq:
        intents = fetch_intents_between(project_id, agent_id, last_synced_seq + 1, current_latest_seq)
        from gods.mnemosyne.semantics import semantics_service
        
        for intent in intents:
            ik = str(getattr(intent, "intent_key", "") or "").strip()
            policy = semantics_service.get_policy(ik) or {}
            
            # Card feed should cover both short-term context and long-term chronicle writes.
            # Otherwise tool.ok (usually to_chronicle=true) appears in full context but disappears in snapshot cards.
            if not (bool(policy.get("to_llm_context", False)) or bool(policy.get("to_chronicle", False))):
                continue

            sk = str(getattr(intent, "source_kind", "") or "").strip()
            seq = int(getattr(intent, "intent_seq", -1) or -1)
            
            # Map into cards
            card_data = _card(
                card_id=f"intent.seq:{seq}",
                kind=sk, # We use sk as kind for context cards
                text=str(getattr(intent, "fallback_text", "") or f"- {ik}"),
                source_seq=seq,
                meta={
                    "intent_key": ik,
                    "source_kind": sk,
                    "runtime_state_sync": True
                }
            )
            # Add required snapshot fields
            card_data["source_intent_ids"] = [str(getattr(intent, "intent_id", "") or f"intent:{seq}")]
            card_data["source_intent_seq_max"] = seq
            
            state["cards"].append(card_data)
            
            if sk == "inbox":
                new_mailbox_count += 1
            elif sk == "event" or sk == "trigger":
                new_trigger_count += 1
                
        state["__chaos_synced_seq"] = current_latest_seq

    return {
        "runtime_meta": {
            "incremental_pull": {
                "new_trigger_count": int(new_trigger_count),
                "new_mailbox_count": int(new_mailbox_count),
                "last_synced_seq": last_synced_seq,
                "current_latest_seq": current_latest_seq,
            }
        }
    }
