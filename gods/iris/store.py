"""Iris unified event JSONL store with project-local file locking."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.iris.models import InboxMessageState, MailEvent, MailEventState
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

_MAIL_EVENT_TYPES = {"mail_event", "inbox_event", "confession", "private", "contract_notice", "contract_fully_committed"}


def _runtime_dir(project_id: str) -> Path:
    path = runtime_dir(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _events_path(project_id: str) -> Path:
    # Single event source for all runtime events.
    return _runtime_dir(project_id) / "events.jsonl"


def _lock_path(project_id: str) -> Path:
    lock_dir = runtime_locks_dir(project_id)
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "events.lock"


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
                return rows, MailEvent.from_dict(row)

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
        row["domain"] = "iris"
        rows.append(row)
        return rows, event

    return _with_locked_rows(project_id, _mut)


def list_mail_events(
    project_id: str,
    agent_id: str = "",
    state: MailEventState | None = None,
    event_type: str = "",
    limit: int = 100,
) -> list[MailEvent]:
    rows = _read_all_rows(_events_path(project_id))
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


def pick_next_mail_event(
    project_id: str,
    agent_id: str,
    now: float,
    cooldown_until: float,
    preempt_types: set[str],
) -> MailEvent | None:
    def _mut(rows: list[dict]):
        candidates: list[dict] = []
        for row in rows:
            if str(row.get("agent_id", "")) != agent_id:
                continue
            if str(row.get("state", "")) != MailEventState.QUEUED.value:
                continue
            if float(row.get("available_at", 0.0) or 0.0) > now:
                continue
            candidates.append(row)

        candidates.sort(key=lambda r: (-int(r.get("priority", 0)), float(r.get("created_at", 0.0))))
        for row in candidates:
            et = str(row.get("event_type", "system"))
            if now < float(cooldown_until or 0.0) and et not in preempt_types:
                continue
            _update_state_fields(row, MailEventState.PICKED, now)
            return rows, MailEvent.from_dict(row)
        return rows, None

    return _with_locked_rows(project_id, _mut)


def mark_mail_processing(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
            if MailEventState.PROCESSING not in _ALLOWED_TRANSITIONS.get(cur, set()):
                return rows, False
            _update_state_fields(row, MailEventState.PROCESSING, now)
            return rows, True
        return rows, False

    return bool(_with_locked_rows(project_id, _mut))


def mark_mail_done(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            _update_state_fields(row, MailEventState.DONE, now)
            row["error_code"] = ""
            row["error_message"] = ""
            return rows, True
        return rows, False

    return bool(_with_locked_rows(project_id, _mut))


def mark_mail_failed_or_requeue(
    project_id: str,
    event_id: str,
    error_code: str,
    error_message: str,
    retry_delay_sec: int = 0,
) -> str:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            attempt = int(row.get("attempt", 0)) + 1
            max_attempts = int(row.get("max_attempts", 3))
            row["attempt"] = attempt
            row["error_code"] = str(error_code or "")
            row["error_message"] = str(error_message or "")[:2000]
            if attempt >= max_attempts:
                _update_state_fields(row, MailEventState.DEAD, now)
                return rows, MailEventState.DEAD.value
            _update_state_fields(row, MailEventState.QUEUED, now)
            row["available_at"] = now + max(0, int(retry_delay_sec))
            return rows, MailEventState.QUEUED.value
        return rows, ""

    return str(_with_locked_rows(project_id, _mut) or "")


def reclaim_stale_mail_processing(project_id: str, timeout_sec: int) -> int:
    now = time.time()
    timeout_sec = max(5, int(timeout_sec))

    def _mut(rows: list[dict]):
        recovered = 0
        for row in rows:
            st = str(row.get("state", ""))
            if st not in {MailEventState.PROCESSING.value, MailEventState.PICKED.value}:
                continue
            picked = float(row.get("picked_at", 0.0) or 0.0)
            if picked <= 0:
                picked = float(row.get("created_at", 0.0) or 0.0)
            if now - picked <= timeout_sec:
                continue
            attempt = int(row.get("attempt", 0)) + 1
            max_attempts = int(row.get("max_attempts", 3))
            row["attempt"] = attempt
            if attempt >= max_attempts:
                _update_state_fields(row, MailEventState.DEAD, now)
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"stale processing timeout > {timeout_sec}s"
            else:
                _update_state_fields(row, MailEventState.QUEUED, now)
                row["available_at"] = now
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"stale processing reclaimed after {timeout_sec}s"
            recovered += 1
        return rows, recovered

    return int(_with_locked_rows(project_id, _mut) or 0)


def retry_mail_event(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            st = str(row.get("state", ""))
            if st not in {MailEventState.DEAD.value, MailEventState.FAILED.value}:
                return rows, False
            _update_state_fields(row, MailEventState.QUEUED, now)
            row["available_at"] = now
            row["error_code"] = ""
            row["error_message"] = ""
            return rows, True
        return rows, False

    return bool(_with_locked_rows(project_id, _mut))


def mark_mail_delivered(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        changed = False
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
            if MailEventState.DELIVERED not in _ALLOWED_TRANSITIONS.get(cur, set()):
                return rows, False
            _update_state_fields(row, MailEventState.DELIVERED, now)
            changed = True
            break
        return rows, changed

    return bool(_with_locked_rows(project_id, _mut))


def mark_mail_handled(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        changed = False
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
            if MailEventState.HANDLED not in _ALLOWED_TRANSITIONS.get(cur, set()):
                return rows, False
            _update_state_fields(row, MailEventState.HANDLED, now)
            changed = True
            break
        return rows, changed

    return bool(_with_locked_rows(project_id, _mut))


# ---- Back-compat wrappers (now backed by unified MailEvent source) ----
def enqueue_inbox_event(
    project_id: str,
    agent_id: str,
    sender: str,
    title: str,
    content: str,
    msg_type: str = "private",
    meta: dict | None = None,
) -> MailEvent:
    return enqueue_mail_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type="mail_event",
        priority=100,
        sender=sender,
        title=title,
        content=content,
        msg_type=msg_type,
        meta=meta,
        payload={"kind": "mail"},
    )


def list_inbox_events(
    project_id: str,
    agent_id: str | None = None,
    state: InboxMessageState | None = None,
    limit: int = 100,
) -> list[MailEvent]:
    mapped_state = MailEventState(state.value) if state else None
    rows = list_mail_events(
        project_id=project_id,
        agent_id=(agent_id or ""),
        state=mapped_state,
        event_type="",
        limit=max(1, limit * 4),
    )
    out = [x for x in rows if x.event_type == "mail_event"]
    out.sort(key=lambda x: x.created_at)
    return out[-max(1, limit) :]


def has_pending_inbox_events(project_id: str, agent_id: str) -> bool:
    rows = _read_all_rows(_events_path(project_id))
    for row in rows:
        if str(row.get("agent_id", "")) != agent_id:
            continue
        if str(row.get("event_type", "")) != "mail_event":
            continue
        if str(row.get("state", "")) in {MailEventState.QUEUED.value, MailEventState.DEFERRED.value}:
            return True
    return False


def transition_inbox_state(project_id: str, event_id: str, target_state: InboxMessageState) -> bool:
    target = MailEventState(target_state.value)
    if target == MailEventState.DELIVERED:
        return mark_mail_delivered(project_id, event_id)
    if target == MailEventState.HANDLED:
        return mark_mail_handled(project_id, event_id)
    if target == MailEventState.DEFERRED:
        now = time.time()

        def _mut(rows: list[dict]):
            for row in rows:
                if str(row.get("event_id", "")) != event_id:
                    continue
                cur = MailEventState(str(row.get("state", MailEventState.QUEUED.value)))
                if MailEventState.DEFERRED not in _ALLOWED_TRANSITIONS.get(cur, set()):
                    return rows, False
                _update_state_fields(row, MailEventState.DEFERRED, now)
                return rows, True
            return rows, False

        return bool(_with_locked_rows(project_id, _mut))
    if target == MailEventState.QUEUED:
        return retry_mail_event(project_id, event_id)
    return False


def take_deliverable_inbox_events(project_id: str, agent_id: str, budget: int) -> list[MailEvent]:
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


def mark_inbox_events_handled(project_id: str, event_ids: list[str]) -> list[MailEvent]:
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
