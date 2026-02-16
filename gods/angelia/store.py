"""Project-local event store for Angelia."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.angelia.models import AgentRunState, AgentRuntimeStatus, AngeliaEvent, AngeliaEventState


def runtime_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def events_path(project_id: str) -> Path:
    return runtime_dir(project_id) / "angelia_events.jsonl"


def agents_path(project_id: str) -> Path:
    return runtime_dir(project_id) / "angelia_agents.json"


def lock_path(project_id: str) -> Path:
    path = runtime_dir(project_id) / "locks" / "angelia_events.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_jsonl(path: Path) -> list[dict]:
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


def _write_jsonl(path: Path, rows: list[dict]):
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
            rows = _read_jsonl(ep)
            new_rows, result = mutator(rows)
            _write_jsonl(ep, new_rows)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


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
    state: AngeliaEventState | None = None,
    event_type: str = "",
    limit: int = 100,
) -> list[AngeliaEvent]:
    rows = _read_jsonl(events_path(project_id))
    out: list[AngeliaEvent] = []
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if state and str(row.get("state", "")) != state.value:
            continue
        if event_type and str(row.get("event_type", "")) != event_type:
            continue
        out.append(AngeliaEvent.from_dict(row))
    out.sort(key=lambda x: (-int(x.priority), float(x.created_at)))
    return out[: max(1, min(limit, 2000))]


def has_queued(project_id: str, agent_id: str) -> bool:
    rows = _read_jsonl(events_path(project_id))
    now = time.time()
    for row in rows:
        if str(row.get("agent_id", "")) != agent_id:
            continue
        if str(row.get("state", "")) != AngeliaEventState.QUEUED.value:
            continue
        if float(row.get("available_at", 0.0) or 0.0) > now:
            continue
        return True
    return False


def count_queued(project_id: str, agent_id: str = "") -> int:
    rows = _read_jsonl(events_path(project_id))
    now = time.time()
    c = 0
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if str(row.get("state", "")) != AngeliaEventState.QUEUED.value:
            continue
        if float(row.get("available_at", 0.0) or 0.0) > now:
            continue
        c += 1
    return c


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
                    AngeliaEventState.QUEUED.value,
                    AngeliaEventState.PICKED.value,
                    AngeliaEventState.PROCESSING.value,
                }:
                    continue
                if float(row.get("created_at", 0.0)) < win_start:
                    continue
                return rows, AngeliaEvent.from_dict(row)

        event = AngeliaEvent(
            event_id=uuid.uuid4().hex,
            project_id=project_id,
            agent_id=agent_id,
            event_type=event_type,
            priority=int(priority),
            state=AngeliaEventState.QUEUED,
            payload=payload,
            dedupe_key=dedupe_key,
            attempt=0,
            max_attempts=max(1, int(max_attempts)),
            created_at=now,
            available_at=now,
        )
        rows.append(event.to_dict())
        return rows, event

    return _with_lock(project_id, _mut)


def pick_next_event(
    project_id: str,
    agent_id: str,
    now: float,
    cooldown_until: float,
    preempt_types: set[str],
) -> AngeliaEvent | None:
    def _mut(rows: list[dict]):
        candidates: list[dict] = []
        for row in rows:
            if str(row.get("agent_id", "")) != agent_id:
                continue
            if str(row.get("state", "")) != AngeliaEventState.QUEUED.value:
                continue
            if float(row.get("available_at", 0.0) or 0.0) > now:
                continue
            candidates.append(row)

        candidates.sort(key=lambda r: (-int(r.get("priority", 0)), float(r.get("created_at", 0.0))))
        for row in candidates:
            et = str(row.get("event_type", "system"))
            if now < float(cooldown_until or 0.0) and et not in preempt_types:
                continue
            row["state"] = AngeliaEventState.PICKED.value
            row["picked_at"] = now
            return rows, AngeliaEvent.from_dict(row)
        return rows, None

    return _with_lock(project_id, _mut)


def mark_processing(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            row["state"] = AngeliaEventState.PROCESSING.value
            row["picked_at"] = now
            return rows, True
        return rows, False

    return bool(_with_lock(project_id, _mut))


def mark_done(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            row["state"] = AngeliaEventState.DONE.value
            row["done_at"] = now
            row["error_code"] = ""
            row["error_message"] = ""
            return rows, True
        return rows, False

    return bool(_with_lock(project_id, _mut))


def mark_failed_or_requeue(project_id: str, event_id: str, error_code: str, error_message: str, retry_delay_sec: int = 0) -> str:
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
                row["state"] = AngeliaEventState.DEAD.value
                row["done_at"] = now
                return rows, AngeliaEventState.DEAD.value
            row["state"] = AngeliaEventState.QUEUED.value
            row["available_at"] = now + max(0, int(retry_delay_sec))
            return rows, AngeliaEventState.QUEUED.value
        return rows, ""

    return str(_with_lock(project_id, _mut) or "")


def retry_event(project_id: str, event_id: str) -> bool:
    now = time.time()

    def _mut(rows: list[dict]):
        for row in rows:
            if str(row.get("event_id", "")) != event_id:
                continue
            st = str(row.get("state", ""))
            if st not in {AngeliaEventState.DEAD.value, AngeliaEventState.FAILED.value}:
                return rows, False
            row["state"] = AngeliaEventState.QUEUED.value
            row["available_at"] = now
            row["error_code"] = ""
            row["error_message"] = ""
            return rows, True
        return rows, False

    return bool(_with_lock(project_id, _mut))


def reclaim_stale_processing(project_id: str, timeout_sec: int) -> int:
    now = time.time()
    timeout_sec = max(5, int(timeout_sec))

    def _mut(rows: list[dict]):
        recovered = 0
        for row in rows:
            st = str(row.get("state", ""))
            if st not in {AngeliaEventState.PROCESSING.value, AngeliaEventState.PICKED.value}:
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
                row["state"] = AngeliaEventState.DEAD.value
                row["done_at"] = now
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"stale processing timeout > {timeout_sec}s"
            else:
                row["state"] = AngeliaEventState.QUEUED.value
                row["available_at"] = now
                row["error_code"] = "PROCESSING_TIMEOUT"
                row["error_message"] = f"recovered from stale processing > {timeout_sec}s"
            recovered += 1
        return rows, recovered

    return int(_with_lock(project_id, _mut) or 0)


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
