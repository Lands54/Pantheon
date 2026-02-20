"""Mnemosyne-owned runtime journal writers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.paths import mnemosyne_dir


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _append_jsonl(path: Path, row: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def inbox_digest_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "inbox_digest" / f"{agent_id}.jsonl"


def record_inbox_digest(project_id: str, agent_id: str, event_ids: list[str], summary: str):
    _append_jsonl(
        inbox_digest_path(project_id, agent_id),
        {
            "project_id": project_id,
            "agent_id": agent_id,
            "event_ids": list(event_ids or []),
            "summary": summary,
            "timestamp": time.time(),
        },
    )
