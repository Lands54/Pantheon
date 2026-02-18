"""Mnemosyne-owned context report readers/writers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.paths import mnemosyne_dir


def context_reports_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "context_reports" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows[-max(1, int(limit)) :]


def list_context_reports(project_id: str, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl(context_reports_path(project_id, agent_id), limit=limit)


def latest_context_report(project_id: str, agent_id: str) -> dict[str, Any] | None:
    rows = list_context_reports(project_id, agent_id, limit=1)
    return rows[-1] if rows else None


def record_context_report(project_id: str, agent_id: str, payload: dict[str, Any]):
    path = context_reports_path(project_id, agent_id)
    row = {
        "project_id": project_id,
        "agent_id": agent_id,
        "timestamp": time.time(),
        **(payload or {}),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
