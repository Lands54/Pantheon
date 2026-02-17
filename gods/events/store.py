"""Unified per-project event bus store backed by events.jsonl."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any

from gods.events.models import EventRecord, EventState
from gods.paths import runtime_dir, runtime_locks_dir

_ALLOWED_TRANSITIONS: dict[EventState, set[EventState]] = {
    EventState.QUEUED: {
        EventState.PICKED,
        EventState.PROCESSING,
        EventState.DONE,
        EventState.FAILED,
        EventState.DEAD,
    },
    EventState.PICKED: {EventState.PROCESSING, EventState.QUEUED, EventState.FAILED, EventState.DEAD},
    EventState.PROCESSING: {EventState.DONE, EventState.QUEUED, EventState.FAILED, EventState.DEAD},
    EventState.DONE: set(),
    EventState.FAILED: {EventState.QUEUED},
    EventState.DEAD: {EventState.QUEUED},
}

_FORBIDDEN_BUSINESS_FIELDS = {
    "delivered_at",
    "handled_at",
    "read_at",
    "mail_state",
    "receipt_state",
    "contract_state",
}


def events_path(project_id: str) -> Path:
    p = runtime_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p / "events.jsonl"


def lock_path(project_id: str) -> Path:
    d = runtime_locks_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / "events.lock"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _write_rows(path: Path, rows: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _with_lock(project_id: str, mutator):
    lp = lock_path(project_id)
    lp.touch(exist_ok=True)
    ep = events_path(project_id)
    with open(lp, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rows = _read_rows(ep)
            rows2, result = mutator(rows)
            _write_rows(ep, rows2)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def append_event(record: EventRecord, dedupe_window_sec: int = 0) -> EventRecord:
    if any(k in (record.payload or {}) for k in _FORBIDDEN_BUSINESS_FIELDS):
        bad = sorted([k for k in (record.payload or {}).keys() if k in _FORBIDDEN_BUSINESS_FIELDS])
        raise ValueError(f"event payload contains forbidden business-state fields: {', '.join(bad)}")
    now = time.time()

    def _mut(rows: list[dict[str, Any]]):
        if record.dedupe_key and dedupe_window_sec > 0:
            win_start = now - float(dedupe_window_sec)
            for row in rows:
                if str(row.get("project_id", "")) != record.project_id:
                    continue
                if str(row.get("event_type", "")) != record.event_type:
                    continue
                if str(row.get("dedupe_key", "")) != record.dedupe_key:
                    continue
                if float(row.get("created_at", 0.0) or 0.0) < win_start:
                    continue
                if str(row.get("state", "")) in {
                    EventState.QUEUED.value,
                    EventState.PICKED.value,
                    EventState.PROCESSING.value,
                }:
                    return rows, EventRecord.from_dict(row)
        rows.append(record.to_dict())
        return rows, record

    return _with_lock(record.project_id, _mut)


def list_events(
    project_id: str,
    domain: str = "",
    event_type: str = "",
    state: EventState | None = None,
    limit: int = 100,
    agent_id: str = "",
) -> list[EventRecord]:
    rows = _read_rows(events_path(project_id))
    out: list[EventRecord] = []
    for row in rows:
        if domain and str(row.get("domain", "")) != domain:
            continue
        if event_type and str(row.get("event_type", "")) != event_type:
            continue
        if state and str(row.get("state", "")) != state.value:
            continue
        if agent_id and str((row.get("payload") or {}).get("agent_id", row.get("agent_id", ""))) != agent_id:
            if str(row.get("agent_id", "")) != agent_id:
                continue
        out.append(EventRecord.from_dict(row))
    out.sort(key=lambda x: (-int(x.priority), float(x.created_at)))
    return out[: max(1, min(limit, 5000))]


def transition_state(project_id: str, event_id: str, target: EventState, *, error_code: str = "", error_message: str = "") -> bool:
    now = time.time()

    def _mut(rows: list[dict[str, Any]]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            cur = EventState(str(row.get("state", EventState.QUEUED.value)))
            if target not in _ALLOWED_TRANSITIONS.get(cur, set()) and target != EventState.DONE:
                return rows, False
            row["state"] = target.value
            if target == EventState.PICKED:
                row["picked_at"] = now
            if target in {EventState.DONE, EventState.FAILED, EventState.DEAD}:
                row["done_at"] = row.get("done_at") or now
            if error_code:
                row["error_code"] = error_code
            if error_message:
                row["error_message"] = error_message[:2000]
            return rows, True
        return rows, False

    return bool(_with_lock(project_id, _mut))


def pick_next(
    project_id: str,
    *,
    domain: str,
    preempt_types: set[str],
    cooldown_until: float,
    now: float,
    owner_id: str = "",
) -> EventRecord | None:
    def _mut(rows: list[dict[str, Any]]):
        cands: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("domain", "")) != domain:
                continue
            if str(row.get("state", "")) != EventState.QUEUED.value:
                continue
            if float(row.get("available_at", 0.0) or 0.0) > now:
                continue
            if owner_id:
                payload = row.get("payload") or {}
                aid = str(payload.get("agent_id", row.get("agent_id", "")))
                if aid != owner_id:
                    continue
            cands.append(row)
        cands.sort(key=lambda r: (-int(r.get("priority", 0)), float(r.get("created_at", 0.0))))
        for row in cands:
            et = str(row.get("event_type", ""))
            if now < float(cooldown_until or 0.0) and et not in preempt_types:
                continue
            row["state"] = EventState.PICKED.value
            row["picked_at"] = now
            return rows, EventRecord.from_dict(row)
        return rows, None

    return _with_lock(project_id, _mut)


def requeue_or_dead(project_id: str, event_id: str, error_code: str, error_message: str, retry_delay_sec: int = 0) -> str:
    now = time.time()

    def _mut(rows: list[dict[str, Any]]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            attempt = int(row.get("attempt", 0)) + 1
            max_attempts = int(row.get("max_attempts", 3))
            row["attempt"] = attempt
            row["error_code"] = str(error_code or "")
            row["error_message"] = str(error_message or "")[:2000]
            if attempt >= max_attempts:
                row["state"] = EventState.DEAD.value
                row["done_at"] = row.get("done_at") or now
                return rows, EventState.DEAD.value
            row["state"] = EventState.QUEUED.value
            row["available_at"] = now + max(0, int(retry_delay_sec))
            return rows, EventState.QUEUED.value
        return rows, ""

    return str(_with_lock(project_id, _mut) or "")


def retry_event(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict[str, Any]]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            st = str(row.get("state", ""))
            if st not in {EventState.DEAD.value, EventState.FAILED.value}:
                return rows, False
            row["state"] = EventState.QUEUED.value
            row["available_at"] = now
            row["error_code"] = ""
            row["error_message"] = ""
            return rows, True
        return rows, False

    return bool(_with_lock(project_id, _mut))


def reconcile_stale(project_id: str, timeout_sec: int, domain: str = "") -> int:
    now = time.time()
    timeout_sec = max(5, int(timeout_sec))

    def _mut(rows: list[dict[str, Any]]):
        recovered = 0
        for row in rows:
            if domain and str(row.get("domain", "")) != domain:
                continue
            st = str(row.get("state", ""))
            if st not in {EventState.PROCESSING.value, EventState.PICKED.value}:
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
                row["state"] = EventState.DEAD.value
                row["done_at"] = row.get("done_at") or now
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"stale processing timeout > {timeout_sec}s"
            else:
                row["state"] = EventState.QUEUED.value
                row["available_at"] = now
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"recovered from stale processing > {timeout_sec}s"
            recovered += 1
        return rows, recovered

    return int(_with_lock(project_id, _mut) or 0)
