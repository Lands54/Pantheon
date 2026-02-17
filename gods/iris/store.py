"""Iris mailbox store with project-local file locking."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods import events as events_bus
from gods.iris.models import MailEvent, MailEventState
from gods.paths import runtime_dir, runtime_locks_dir

_ALLOWED_TRANSITIONS: dict[MailEventState, set[MailEventState]] = {
    MailEventState.QUEUED: {
        MailEventState.PICKED,
        MailEventState.PROCESSING,
        MailEventState.DELIVERED,
        MailEventState.DEFERRED,
        MailEventState.HANDLED,
        MailEventState.DONE,
        MailEventState.FAILED,
        MailEventState.DEAD,
    },
    MailEventState.PICKED: {MailEventState.PROCESSING, MailEventState.QUEUED, MailEventState.DEAD, MailEventState.FAILED},
    MailEventState.PROCESSING: {MailEventState.DONE, MailEventState.QUEUED, MailEventState.DEAD, MailEventState.FAILED},
    MailEventState.DELIVERED: {MailEventState.HANDLED},
    MailEventState.DEFERRED: {MailEventState.DELIVERED, MailEventState.HANDLED, MailEventState.QUEUED},
    MailEventState.HANDLED: set(),
    MailEventState.DONE: set(),
    MailEventState.FAILED: {MailEventState.QUEUED},
    MailEventState.DEAD: {MailEventState.QUEUED},
}

_MAIL_EVENT_TYPES = {"mail_event", "confession", "private", "contract_notice", "contract_fully_committed"}


def _runtime_dir(project_id: str) -> Path:
    path = runtime_dir(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mailbox_path(project_id: str) -> Path:
    return _runtime_dir(project_id) / "mailbox_events.jsonl"


def _lock_path(project_id: str) -> Path:
    lock_dir = runtime_locks_dir(project_id)
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "mailbox_events.lock"


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
    events = _mailbox_path(project_id)
    with open(lock, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rows = _read_all_rows(events)
            new_rows, result = mutator(rows)
            _write_all_rows(events, new_rows)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _mail_event_match(row: dict) -> bool:
    et = str(row.get("event_type", ""))
    return et in _MAIL_EVENT_TYPES


def _update_state_fields(row: dict, target_state: MailEventState, now: float):
    row["state"] = target_state.value
    if target_state == MailEventState.PICKED:
        row["picked_at"] = now
    elif target_state == MailEventState.PROCESSING:
        row["picked_at"] = row.get("picked_at") or now
    elif target_state == MailEventState.DELIVERED:
        row["delivered_at"] = now
    elif target_state == MailEventState.HANDLED:
        row["handled_at"] = now
    elif target_state in {MailEventState.DONE, MailEventState.DEAD, MailEventState.FAILED}:
        row["done_at"] = row.get("done_at") or now


def enqueue_mail_event(
    project_id: str,
    agent_id: str,
    event_type: str,
    priority: int,
    payload: dict | None = None,
    sender: str = "",
    title: str = "",
    content: str = "",
    msg_type: str = "private",
    dedupe_key: str = "",
    max_attempts: int = 3,
    dedupe_window_sec: int = 0,
    meta: dict | None = None,
) -> MailEvent:
    now = time.time()
    payload = payload or {}
    dedupe_key = str(dedupe_key or "").strip()

    def _mut(rows: list[dict]):
        if dedupe_key and dedupe_window_sec > 0:
            win_start = now - float(dedupe_window_sec)
            for row in rows:
                if str(row.get("agent_id", "")) != agent_id:
                    continue
                if str(row.get("dedupe_key", "")) != dedupe_key:
                    continue
                if str(row.get("state", "")) not in {
                    MailEventState.QUEUED.value,
                    MailEventState.PICKED.value,
                    MailEventState.PROCESSING.value,
                    MailEventState.DEFERRED.value,
                }:
                    continue
                if float(row.get("created_at", 0.0)) < win_start:
                    continue
                return rows, (MailEvent.from_dict(row), False)

        event = MailEvent(
            event_id=uuid.uuid4().hex,
            project_id=project_id,
            agent_id=agent_id,
            event_type=str(event_type or "mail_event").strip() or "mail_event",
            priority=int(priority),
            created_at=now,
            state=MailEventState.QUEUED,
            payload=payload,
            sender=sender,
            title=title,
            msg_type=msg_type,
            content=content,
            dedupe_key=dedupe_key,
            attempt=0,
            max_attempts=max(1, int(max_attempts)),
            available_at=now,
            meta=meta or {},
        )
        row = event.to_dict()
        rows.append(row)
        return rows, (event, True)

    event, created = _with_locked_rows(project_id, _mut)
    if created:
        bus_row = events_bus.EventRecord.create(
            project_id=project_id,
            domain="iris",
            event_type=str(event.event_type or "mail_event"),
            priority=int(event.priority),
            payload={
                "agent_id": event.agent_id,
                "sender": event.sender,
                "title": event.title,
                "content": event.content,
                "msg_type": event.msg_type,
                "reason": str((event.payload or {}).get("reason", "mail_event")),
                "source": str((event.payload or {}).get("source", "iris")),
            },
            dedupe_key=event.dedupe_key,
            max_attempts=int(event.max_attempts),
            event_id=event.event_id,
            meta=event.meta or {},
        )
        events_bus.append_event(bus_row)
    return event


def list_mail_events(
    project_id: str,
    agent_id: str = "",
    state: MailEventState | None = None,
    event_type: str = "",
    limit: int = 100,
) -> list[MailEvent]:
    rows = _read_all_rows(_mailbox_path(project_id))
    out: list[MailEvent] = []
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if state and str(row.get("state", "")) != state.value:
            continue
        if event_type and str(row.get("event_type", "")) != event_type:
            continue
        out.append(MailEvent.from_dict(row))
    out.sort(key=lambda x: (-int(x.priority), float(x.created_at)))
    return out[: max(1, min(limit, 2000))]


def list_mailbox_events(
    project_id: str,
    agent_id: str,
    state: MailEventState | None = None,
    limit: int = 100,
) -> list[MailEvent]:
    rows = list_mail_events(
        project_id=project_id,
        agent_id=agent_id,
        state=state,
        event_type="mail_event",
        limit=max(1, limit),
    )
    rows.sort(key=lambda x: x.created_at)
    return rows[-max(1, limit) :]


def has_pending_mailbox_events(project_id: str, agent_id: str) -> bool:
    rows = _read_all_rows(_mailbox_path(project_id))
    for row in rows:
        if str(row.get("agent_id", "")) != agent_id:
            continue
        if str(row.get("event_type", "")) != "mail_event":
            continue
        if str(row.get("state", "")) in {MailEventState.QUEUED.value, MailEventState.DEFERRED.value}:
            return True
    return False


def deliver_mailbox_events(project_id: str, agent_id: str, budget: int) -> list[MailEvent]:
    budget = max(1, int(budget))
    now = time.time()

    def _mut(rows: list[dict]):
        deliverable: list[dict] = []
        overflow: list[dict] = []
        for row in rows:
            if str(row.get("agent_id", "")) != agent_id:
                continue
            if str(row.get("event_type", "")) != "mail_event":
                continue
            state = str(row.get("state", ""))
            if state not in {MailEventState.QUEUED.value, MailEventState.DEFERRED.value}:
                continue
            if float(row.get("available_at", 0.0) or 0.0) > now:
                continue
            if len(deliverable) < budget:
                deliverable.append(row)
            else:
                overflow.append(row)

        for row in deliverable:
            _update_state_fields(row, MailEventState.DELIVERED, now)
        for row in overflow:
            cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
            if MailEventState.DEFERRED in _ALLOWED_TRANSITIONS.get(cur, set()):
                _update_state_fields(row, MailEventState.DEFERRED, now)

        events = [MailEvent.from_dict(r) for r in deliverable]
        events.sort(key=lambda x: x.created_at)
        return rows, events

    return list(_with_locked_rows(project_id, _mut) or [])


def mark_mailbox_events_handled(project_id: str, event_ids: list[str]) -> list[MailEvent]:
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
            if str(row.get("event_type", "")) != "mail_event":
                continue
            cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
            if MailEventState.HANDLED in _ALLOWED_TRANSITIONS.get(cur, set()):
                _update_state_fields(row, MailEventState.HANDLED, now)
                changed_rows.append(dict(row))
        return rows, changed_rows

    changed = list(_with_locked_rows(project_id, _mut) or [])
    return [MailEvent.from_dict(row) for row in changed]
