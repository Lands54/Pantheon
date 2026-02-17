"""Angelia store: scheduler runtime status + EventBus-backed event access."""
from __future__ import annotations

import json
from pathlib import Path

from gods import events as events_bus
from gods.angelia.models import AgentRuntimeStatus, AngeliaEvent


def runtime_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def agents_path(project_id: str) -> Path:
    return runtime_dir(project_id) / "angelia_agents.json"


def _load_agent_statuses(project_id: str) -> dict[str, dict]:
    ap = agents_path(project_id)
    if not ap.exists():
        return {}
    try:
        raw = json.loads(ap.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def _save_agent_statuses(project_id: str, payload: dict[str, dict]):
    ap = agents_path(project_id)
    ap.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_events(
    project_id: str,
    agent_id: str = "",
    state=None,
    event_type: str = "",
    limit: int = 100,
) -> list[AngeliaEvent]:
    st = None
    if state is not None:
        try:
            st = events_bus.EventState(state.value)
        except Exception:
            return []
    rows = events_bus.list_events(
        project_id=project_id,
        domain="",
        event_type=event_type,
        state=st,
        limit=limit,
        agent_id=agent_id,
    )
    out: list[AngeliaEvent] = []
    for row in rows:
        payload = row.payload or {}
        rid = str(payload.get("agent_id", ""))
        raw = row.to_dict()
        raw["agent_id"] = rid
        out.append(AngeliaEvent.from_dict(raw))
    return out


def has_queued(project_id: str, agent_id: str) -> bool:
    rows = events_bus.list_events(
        project_id=project_id,
        domain="",
        event_type="",
        state=events_bus.EventState.QUEUED,
        limit=1,
        agent_id=agent_id,
    )
    return bool(rows)


def count_queued(project_id: str, agent_id: str = "") -> int:
    rows = events_bus.list_events(
        project_id=project_id,
        domain="",
        event_type="",
        state=events_bus.EventState.QUEUED,
        limit=2000,
        agent_id=agent_id,
    )
    return len(rows)


def enqueue_event(
    project_id: str,
    agent_id: str,
    event_type: str,
    priority: int,
    payload: dict | None = None,
    dedupe_key: str = "",
    max_attempts: int = 3,
    dedupe_window_sec: int = 0,
) -> AngeliaEvent:
    event = events_bus.EventRecord.create(
        project_id=project_id,
        domain="angelia",
        event_type=event_type,
        priority=priority,
        payload={"agent_id": agent_id, **(payload or {})},
        dedupe_key=dedupe_key,
        max_attempts=max_attempts,
    )
    event = events_bus.append_event(event, dedupe_window_sec=dedupe_window_sec)
    raw = event.to_dict()
    raw["agent_id"] = agent_id
    return AngeliaEvent.from_dict(raw)


def pick_next_event(
    project_id: str,
    agent_id: str,
    now: float,
    cooldown_until: float,
    preempt_types: set[str],
) -> AngeliaEvent | None:
    rows = events_bus.list_events(
        project_id=project_id,
        state=events_bus.EventState.QUEUED,
        limit=5000,
        agent_id=agent_id,
    )
    cand = None
    for row in rows:
        if now < float(cooldown_until or 0.0) and str(row.event_type or "") not in preempt_types:
            continue
        cand = row
        break
    if cand is None:
        return None
    ok = events_bus.transition_state(project_id, cand.event_id, events_bus.EventState.PICKED)
    if not ok:
        return None
    raw = cand.to_dict()
    raw["state"] = events_bus.EventState.PICKED.value
    raw["agent_id"] = str((cand.payload or {}).get("agent_id", ""))
    return AngeliaEvent.from_dict(raw)


def mark_processing(project_id: str, event_id: str) -> bool:
    return bool(events_bus.transition_state(project_id, event_id, events_bus.EventState.PROCESSING))


def mark_done(project_id: str, event_id: str) -> bool:
    return bool(events_bus.transition_state(project_id, event_id, events_bus.EventState.DONE))


def mark_failed_or_requeue(project_id: str, event_id: str, error_code: str, error_message: str, retry_delay_sec: int = 0) -> str:
    return str(events_bus.requeue_or_dead(project_id, event_id, error_code, error_message, retry_delay_sec) or "")


def retry_event(project_id: str, event_id: str) -> bool:
    return bool(events_bus.retry_event(project_id, event_id))


def reclaim_stale_processing(project_id: str, timeout_sec: int) -> int:
    return int(events_bus.reconcile_stale(project_id, timeout_sec) or 0)


def get_agent_status(project_id: str, agent_id: str) -> AgentRuntimeStatus:
    raw = _load_agent_statuses(project_id)
    row = raw.get(agent_id)
    if not isinstance(row, dict):
        return AgentRuntimeStatus(project_id=project_id, agent_id=agent_id)
    return AgentRuntimeStatus.from_dict(row)


def set_agent_status(project_id: str, status: AgentRuntimeStatus):
    raw = _load_agent_statuses(project_id)
    raw[status.agent_id] = status.to_dict()
    _save_agent_statuses(project_id, raw)


def list_agent_status(project_id: str, agent_ids: list[str]) -> list[AgentRuntimeStatus]:
    raw = _load_agent_statuses(project_id)
    out: list[AgentRuntimeStatus] = []
    for aid in agent_ids:
        row = raw.get(aid)
        if isinstance(row, dict):
            out.append(AgentRuntimeStatus.from_dict(row))
        else:
            out.append(AgentRuntimeStatus(project_id=project_id, agent_id=aid))
    return out
