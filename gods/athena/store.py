"""Storage helpers for Athena flow runs."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any

from gods.paths import runtime_dir, runtime_locks_dir


def runs_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "athena_runs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def lock_path(project_id: str) -> Path:
    p = runtime_locks_dir(project_id) / "athena.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "athena_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("", encoding="utf-8")
    return p


def load_runs(project_id: str) -> list[dict[str, Any]]:
    p = runs_path(project_id)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            rows = raw.get("runs", [])
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    except Exception:
        return []
    return []


def save_runs(project_id: str, runs: list[dict[str, Any]]) -> None:
    p = runs_path(project_id)
    payload = {
        "version": 1,
        "updated_at": float(time.time()),
        "runs": list(runs or []),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def with_lock(project_id: str, mutator):
    lp = lock_path(project_id)
    lp.touch(exist_ok=True)
    with lp.open("r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            rows = load_runs(project_id)
            next_rows, result = mutator(rows)
            save_runs(project_id, next_rows)
            return result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append_ledger(project_id: str, row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row or {})
    payload.setdefault("ts", float(time.time()))
    with ledger_path(project_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def list_ledger(project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
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
            if isinstance(row, dict):
                out.append(row)
    return out[-max(1, min(int(limit or 200), 5000)):]
