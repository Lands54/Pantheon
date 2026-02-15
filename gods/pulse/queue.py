"""Pulse queue store and operations."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.pulse.models import PulseEvent, PulseEventStatus


_VALID_EVENT_TYPES = {"inbox_event", "timer", "manual", "system"}


def _runtime_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _events_path(project_id: str) -> Path:
    return _runtime_dir(project_id) / "pulse_events.jsonl"


def _lock_path(project_id: str) -> Path:
    lock_dir = _runtime_dir(project_id) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "pulse_events.lock"


def _read_all_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _write_all_rows(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _with_locked_rows(project_id: str, mutator):
    lock = _lock_path(project_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)
    events = _events_path(project_id)
    with open(lock, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rows = _read_all_rows(events)
            new_rows, result = mutator(rows)
            _write_all_rows(events, new_rows)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _same_payload(a: dict | None, b: dict | None) -> bool:
    return (a or {}) == (b or {})


def enqueue_pulse_event(
    project_id: str,
    agent_id: str,
    event_type: str,
    priority: int,
    payload: dict | None = None,
) -> PulseEvent:
    if event_type not in _VALID_EVENT_TYPES:
        event_type = "system"
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("agent_id", "")) != agent_id:
                continue
            if str(row.get("event_type", "")) != event_type:
                continue
            if str(row.get("status", "")) != PulseEventStatus.QUEUED.value:
                continue
            if _same_payload(row.get("payload") or {}, payload or {}):
                return rows, PulseEvent.from_dict(row)

        event = PulseEvent(
            event_id=uuid.uuid4().hex,
            project_id=project_id,
            agent_id=agent_id,
            event_type=event_type,
            priority=int(priority),
            created_at=now,
            status=PulseEventStatus.QUEUED,
            payload=payload or {},
        )
        rows.append(event.to_dict())
        return rows, event

    return _with_locked_rows(project_id, _mut)


def list_pulse_events(
    project_id: str,
    agent_id: str | None = None,
    status: PulseEventStatus | None = None,
    limit: int = 100,
) -> list[PulseEvent]:
    rows = _read_all_rows(_events_path(project_id))
    out: list[PulseEvent] = []
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if status and str(row.get("status", "")) != status.value:
            continue
        out.append(PulseEvent.from_dict(row))
    out.sort(key=lambda x: (-x.priority, x.created_at))
    return out[: max(1, limit)]


def count_queued_events(project_id: str, active_agents: list[str]) -> int:
    aset = set(active_agents)
    rows = _read_all_rows(_events_path(project_id))
    total = 0
    for row in rows:
        if str(row.get("agent_id", "")) not in aset:
            continue
        if str(row.get("status", "")) == PulseEventStatus.QUEUED.value:
            total += 1
    return total


def pick_pulse_events(project_id: str, active_agents: list[str], batch_size: int) -> list[PulseEvent]:
    aset = set(active_agents)
    batch_size = max(1, int(batch_size))
    now = time.time()

    def _mut(rows: list[dict]):
        candidates: list[dict] = []
        for row in rows:
            if str(row.get("status", "")) != PulseEventStatus.QUEUED.value:
                continue
            if str(row.get("agent_id", "")) not in aset:
                continue
            candidates.append(row)

        candidates.sort(key=lambda r: (-int(r.get("priority", 0)), float(r.get("created_at", 0.0))))

        picked_rows: list[dict] = []
        seen_agent: set[str] = set()
        for row in candidates:
            aid = str(row.get("agent_id", ""))
            if aid in seen_agent:
                continue
            seen_agent.add(aid)
            row["status"] = PulseEventStatus.PICKED.value
            row["picked_at"] = now
            picked_rows.append(row)
            if len(picked_rows) >= batch_size:
                break

        return rows, [PulseEvent.from_dict(r) for r in picked_rows]

    return list(_with_locked_rows(project_id, _mut) or [])


def mark_pulse_event_done(project_id: str, event_id: str, dropped: bool = False):
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            row["status"] = PulseEventStatus.DROPPED.value if dropped else PulseEventStatus.DONE.value
            row["done_at"] = now
            break
        return rows, True

    _with_locked_rows(project_id, _mut)
