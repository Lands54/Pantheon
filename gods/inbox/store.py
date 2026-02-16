"""Inbox JSONL store with project-local file locking."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.inbox.models import InboxEvent, InboxMessageState

_ALLOWED_TRANSITIONS: dict[InboxMessageState, set[InboxMessageState]] = {
    InboxMessageState.PENDING: {InboxMessageState.DELIVERED, InboxMessageState.DEFERRED, InboxMessageState.HANDLED},
    InboxMessageState.DEFERRED: {InboxMessageState.DELIVERED, InboxMessageState.HANDLED},
    InboxMessageState.DELIVERED: {InboxMessageState.HANDLED},
    InboxMessageState.HANDLED: set(),
}


def _runtime_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _events_path(project_id: str) -> Path:
    return _runtime_dir(project_id) / "inbox_events.jsonl"


def _lock_path(project_id: str) -> Path:
    lock_dir = _runtime_dir(project_id) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "inbox_events.lock"


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


def enqueue_inbox_event(
    project_id: str,
    agent_id: str,
    sender: str,
    title: str,
    content: str,
    msg_type: str = "private",
    meta: dict | None = None,
) -> InboxEvent:
    now = time.time()
    event = InboxEvent(
        event_id=uuid.uuid4().hex,
        project_id=project_id,
        agent_id=agent_id,
        sender=sender,
        title=title,
        msg_type=msg_type,
        content=content,
        created_at=now,
        state=InboxMessageState.PENDING,
        meta=meta or {},
    )

    def _mut(rows: list[dict]):
        rows.append(event.to_dict())
        return rows, event

    return _with_locked_rows(project_id, _mut)


def list_inbox_events(
    project_id: str,
    agent_id: str | None = None,
    state: InboxMessageState | None = None,
    limit: int = 100,
) -> list[InboxEvent]:
    rows = _read_all_rows(_events_path(project_id))
    out: list[InboxEvent] = []
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if state and str(row.get("state", "")) != state.value:
            continue
        out.append(InboxEvent.from_dict(row))
    out.sort(key=lambda x: x.created_at)
    return out[-max(1, limit) :]


def has_pending_inbox_events(project_id: str, agent_id: str) -> bool:
    rows = _read_all_rows(_events_path(project_id))
    for row in rows:
        if str(row.get("agent_id", "")) != agent_id:
            continue
        if str(row.get("state", "")) in {InboxMessageState.PENDING.value, InboxMessageState.DEFERRED.value}:
            return True
    return False


def _update_state_fields(row: dict, target_state: InboxMessageState, now: float):
    row["state"] = target_state.value
    if target_state == InboxMessageState.DELIVERED:
        row["delivered_at"] = now
    if target_state == InboxMessageState.HANDLED:
        row["handled_at"] = now


def transition_inbox_state(project_id: str, event_id: str, target_state: InboxMessageState) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        changed = False
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            current = InboxMessageState(str(row.get("state", InboxMessageState.PENDING.value)))
            if target_state in _ALLOWED_TRANSITIONS.get(current, set()):
                _update_state_fields(row, target_state, now)
                changed = True
            break
        return rows, changed

    return bool(_with_locked_rows(project_id, _mut))


def take_deliverable_inbox_events(project_id: str, agent_id: str, budget: int) -> list[InboxEvent]:
    budget = max(1, int(budget))
    now = time.time()

    def _mut(rows: list[dict]):
        deliverable: list[dict] = []
        overflow: list[dict] = []
        for row in rows:
            if str(row.get("agent_id", "")) != agent_id:
                continue
            state = str(row.get("state", ""))
            if state not in {InboxMessageState.PENDING.value, InboxMessageState.DEFERRED.value}:
                continue
            if len(deliverable) < budget:
                deliverable.append(row)
            else:
                overflow.append(row)

        for row in deliverable:
            _update_state_fields(row, InboxMessageState.DELIVERED, now)
        for row in overflow:
            current = InboxMessageState(str(row.get("state", InboxMessageState.PENDING.value)))
            if InboxMessageState.DEFERRED in _ALLOWED_TRANSITIONS.get(current, set()):
                _update_state_fields(row, InboxMessageState.DEFERRED, now)

        events = [InboxEvent.from_dict(r) for r in deliverable]
        events.sort(key=lambda x: x.created_at)
        return rows, events

    return list(_with_locked_rows(project_id, _mut) or [])


def mark_inbox_events_handled(project_id: str, event_ids: list[str]) -> list[InboxEvent]:
    ids = {str(x) for x in (event_ids or []) if x}
    if not ids:
        return []
    now = time.time()

    def _mut(rows: list[dict]):
        changed_rows: list[dict] = []
        for row in rows:
            eid = str(row.get("event_id", ""))
            if eid not in ids:
                continue
            current = InboxMessageState(str(row.get("state", InboxMessageState.PENDING.value)))
            if InboxMessageState.HANDLED in _ALLOWED_TRANSITIONS.get(current, set()):
                _update_state_fields(row, InboxMessageState.HANDLED, now)
                changed_rows.append(dict(row))
        return rows, changed_rows

    changed = list(_with_locked_rows(project_id, _mut) or [])
    return [InboxEvent.from_dict(row) for row in changed]
