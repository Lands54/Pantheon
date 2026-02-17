"""Angelia store: scheduler runtime status + Iris-backed event access."""
from __future__ import annotations

import json
from pathlib import Path

from gods.angelia.models import AgentRuntimeStatus, AngeliaEvent
from gods.iris import facade as iris_facade


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
    state_val = state.value if state is not None else ""
    rows = iris_facade.list_mail_runtime_events(
        project_id=project_id,
        agent_id=agent_id,
        state=state_val,
        event_type=event_type,
        limit=limit,
    )
    return [AngeliaEvent.from_dict(row) for row in rows]


def has_queued(project_id: str, agent_id: str) -> bool:
    rows = iris_facade.list_mail_runtime_events(
        project_id=project_id,
        agent_id=agent_id,
        state="queued",
        event_type="",
        limit=1,
    )
    return bool(rows)


def count_queued(project_id: str, agent_id: str = "") -> int:
    rows = iris_facade.list_mail_runtime_events(
        project_id=project_id,
        agent_id=agent_id,
        state="queued",
        event_type="",
        limit=2000,
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
    event = iris_facade.enqueue_mail_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type=event_type,
        priority=priority,
        payload=payload or {},
        dedupe_key=dedupe_key,
        max_attempts=max_attempts,
        dedupe_window_sec=dedupe_window_sec,
    )
    return AngeliaEvent.from_dict(event.to_dict())


def pick_next_event(
    project_id: str,
    agent_id: str,
    now: float,
    cooldown_until: float,
    preempt_types: set[str],
) -> AngeliaEvent | None:
    row = iris_facade.pick_mail_event(project_id, agent_id, now, cooldown_until, preempt_types)
    if row is None:
        return None
    return AngeliaEvent.from_dict(row.to_dict())


def mark_processing(project_id: str, event_id: str) -> bool:
    return bool(iris_facade.mark_processing(project_id, event_id))


def mark_done(project_id: str, event_id: str) -> bool:
    return bool(iris_facade.mark_done(project_id, event_id))


def mark_failed_or_requeue(project_id: str, event_id: str, error_code: str, error_message: str, retry_delay_sec: int = 0) -> str:
    return str(
        iris_facade.mark_failed_or_requeue(
            project_id,
            event_id,
            error_code,
            error_message,
            retry_delay_sec,
        )
        or ""
    )


def retry_event(project_id: str, event_id: str) -> bool:
    return bool(iris_facade.retry_event(project_id, event_id))


def reclaim_stale_processing(project_id: str, timeout_sec: int) -> int:
    return int(iris_facade.reclaim_stale_processing(project_id, timeout_sec) or 0)


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
