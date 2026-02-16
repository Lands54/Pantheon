"""Scheduler compatibility layer backed by Angelia."""
from __future__ import annotations

import time
from typing import Dict, List, Tuple

from gods.angelia.scheduler import angelia_supervisor
from gods.angelia import store
from gods.angelia.models import AgentRunState, AgentRuntimeStatus, AngeliaEventState
from gods.config import runtime_config

# Legacy in-process cache kept for unit-test compatibility helpers.
_META: Dict[Tuple[str, str], dict] = {}


def _key(project_id: str, agent_id: str) -> Tuple[str, str]:
    return (project_id, agent_id)


def _status_from_agent(st: AgentRuntimeStatus) -> dict:
    return {
        "project_id": st.project_id,
        "agent_id": st.agent_id,
        "status": st.run_state.value,
        "last_reason": st.current_event_type,
        "last_pulse_at": float(st.last_wake_at or 0.0),
        "next_eligible_at": float(st.cooldown_until or st.backoff_until or 0.0),
        "empty_cycles": 0,
        "last_next_step": "",
        "last_error": st.last_error,
        "last_timer_emit_at": 0.0,
    }


def _get_status(project_id: str, agent_id: str) -> dict:
    st = _status_from_agent(store.get_agent_status(project_id, agent_id))
    key = _key(project_id, agent_id)
    merged = dict(st)
    merged.update(_META.get(key, {}))
    _META[key] = merged
    return merged


def has_pending_inbox(project_id: str, agent_id: str) -> bool:
    from gods.inbox import has_pending

    return has_pending(project_id, agent_id)


def pulse_agent_sync(
    project_id: str,
    agent_id: str,
    reason: str,
    force: bool = False,
    pulse_event_id: str = "",
) -> dict:
    _ = force
    _ = pulse_event_id
    evt = angelia_supervisor.enqueue_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type="manual",
        payload={"reason": reason or "manual"},
    )
    return {"triggered": True, "reason": reason, "event_id": evt.get("event_id", "")}


def get_project_status(project_id: str, active_agents: List[str]) -> List[dict]:
    rows = angelia_supervisor.list_agent_status(project_id, active_agents)
    now = time.time()
    out: List[dict] = []
    for row in rows:
        item = {
            "project_id": project_id,
            "agent_id": row.get("agent_id", ""),
            "status": row.get("run_state", AgentRunState.IDLE.value),
            "last_reason": row.get("current_event_type", ""),
            "last_pulse_at": float(row.get("last_wake_at", 0.0) or 0.0),
            "next_eligible_at": max(float(row.get("cooldown_until", 0.0) or 0.0), float(row.get("backoff_until", 0.0) or 0.0)),
            "empty_cycles": 0,
            "last_next_step": "",
            "last_error": row.get("last_error", ""),
            "queued_pulse_events": int(row.get("queued_events", 0)),
            "has_pending_inbox": has_pending_inbox(project_id, row.get("agent_id", "")),
            "now": now,
        }
        out.append(item)
    return out


def _enqueue_idle_timer_events(project_id: str, active_agents: List[str], now: float):
    _ = now
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return
    if not bool(getattr(proj, "angelia_timer_enabled", True)):
        return
    for aid in active_agents:
        st = _get_status(project_id, aid)
        if st.get("status") == AgentRunState.RUNNING.value:
            continue
        if store.count_queued(project_id, aid) > 0:
            continue
        event = angelia_supervisor.enqueue_event(
            project_id=project_id,
            agent_id=aid,
            event_type="timer",
            payload={"reason": "idle_heartbeat", "source": "scheduler_compat"},
            dedupe_key=f"timer:{aid}",
        )
        st["last_timer_emit_at"] = float(event.get("created_at", time.time()))
        _META[_key(project_id, aid)] = st


def pick_pulse_batch(project_id: str, active_agents: List[str], batch_size: int) -> List[Tuple[str, str, str]]:
    if not active_agents:
        return []

    now = time.time()
    if sum(store.count_queued(project_id, aid) for aid in active_agents) <= 0:
        _enqueue_idle_timer_events(project_id, active_agents, now)

    out: List[Tuple[str, str, str]] = []
    limit = max(1, int(batch_size))
    for aid in active_agents:
        if len(out) >= limit:
            break
        st = store.get_agent_status(project_id, aid)
        evt = store.pick_next_event(
            project_id=project_id,
            agent_id=aid,
            now=now,
            cooldown_until=max(float(st.cooldown_until or 0.0), float(st.backoff_until or 0.0)),
            preempt_types={"inbox_event", "manual"},
        )
        if not evt:
            continue
        reason = str(evt.payload.get("reason") or evt.event_type)
        out.append((aid, reason, evt.event_id))
    return out


def push_manual_pulse(project_id: str, agent_id: str, event_type: str = "manual", payload: dict | None = None) -> dict:
    evt = angelia_supervisor.enqueue_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type=event_type or "manual",
        payload=payload or {},
        dedupe_key="",
    )
    return {
        "event_id": evt.get("event_id", ""),
        "project_id": project_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "status": AngeliaEventState.QUEUED.value,
        "payload": payload or {},
        "created_at": evt.get("created_at", 0.0),
    }
