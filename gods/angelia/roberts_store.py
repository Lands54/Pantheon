"""Storage layer for Robert Rules council state/ledger/resolution."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any

from gods.angelia.roberts_models import MeetingState
from gods.paths import runtime_dir, runtime_locks_dir


def state_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "sync_council.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def lock_path(project_id: str) -> Path:
    p = runtime_locks_dir(project_id) / "sync_council.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "sync_council_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("", encoding="utf-8")
    return p


def resolutions_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "sync_council_resolutions.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("", encoding="utf-8")
    return p


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def load_state(project_id: str) -> MeetingState:
    return MeetingState.from_dict(_read_json(state_path(project_id)))


def save_state(project_id: str, state: MeetingState | dict[str, Any]) -> MeetingState:
    payload = state.to_dict() if isinstance(state, MeetingState) else MeetingState.from_dict(state).to_dict()
    payload["updated_at"] = float(time.time())
    state_path(project_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return MeetingState.from_dict(payload)


def with_state_lock(project_id: str, mutator):
    lp = lock_path(project_id)
    lp.touch(exist_ok=True)
    with lp.open("r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            current = load_state(project_id)
            next_state, result = mutator(current)
            saved = save_state(project_id, next_state)
            return saved, result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _next_ledger_seq(project_id: str) -> int:
    p = ledger_path(project_id)
    seq = 0
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                seq = max(seq, int(row.get("seq", 0) or 0))
    except Exception:
        return 1
    return seq + 1


def append_ledger(
    project_id: str,
    *,
    session_id: str,
    phase: str,
    actor_id: str,
    action_type: str,
    payload: dict[str, Any] | None,
    target_motion_id: str = "",
    result: str = "ok",
    error: str = "",
) -> dict[str, Any]:
    row = {
        "seq": _next_ledger_seq(project_id),
        "ts": float(time.time()),
        "project_id": project_id,
        "session_id": str(session_id or ""),
        "phase": str(phase or ""),
        "actor_id": str(actor_id or ""),
        "action_type": str(action_type or ""),
        "target_motion_id": str(target_motion_id or ""),
        "payload": dict(payload or {}),
        "result": str(result or "ok"),
        "error": str(error or ""),
    }
    with ledger_path(project_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_ledger(project_id: str, *, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with ledger_path(project_id).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if int(row.get("seq", 0) or 0) <= int(since_seq or 0):
                continue
            out.append(row)
    out.sort(key=lambda x: int(x.get("seq", 0) or 0))
    return out[: max(1, min(int(limit or 200), 2000))]


def append_resolution(project_id: str, row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row or {})
    payload.setdefault("created_at", float(time.time()))
    with resolutions_path(project_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def list_resolutions(project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with resolutions_path(project_id).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            out.append(row)
    out.sort(key=lambda x: float(x.get("created_at", 0.0) or 0.0), reverse=True)
    return out[: max(1, min(int(limit or 200), 2000))]
