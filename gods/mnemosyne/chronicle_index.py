"""Mnemosyne chronicle index (structured long-term memory view)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gods.mnemosyne.compaction import chronicle_path
from gods.paths import mnemosyne_dir


def _index_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "chronicle_index" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_chronicle_index_entry(project_id: str, agent_id: str, row: dict[str, Any]) -> None:
    path = _index_path(project_id, agent_id)
    payload = dict(row or {})
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_chronicle_index_entries(project_id: str, agent_id: str, limit: int = 300) -> list[dict[str, Any]]:
    path = _index_path(project_id, agent_id)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    if limit <= 0:
        return []
    return rows[-max(1, min(int(limit), 5000)) :]


def list_chronicle_index_texts(project_id: str, agent_id: str, limit: int = 300) -> list[str]:
    out: list[str] = []
    for row in list_chronicle_index_entries(project_id, agent_id, limit=limit):
        text = str(row.get("rendered", "") or "").strip()
        if text:
            out.append(text)
    return out


def rebuild_chronicle_markdown_from_index(project_id: str, agent_id: str) -> dict[str, Any]:
    rows = list_chronicle_index_entries(project_id, agent_id, limit=5000)
    lines: list[str] = []
    for row in rows:
        ts = str(row.get("timestamp", ""))
        key = str(row.get("intent_key", ""))
        src_id = str(row.get("source_intent_id", "") or "")
        text = str(row.get("rendered", "") or "").strip()
        if not text:
            continue
        if src_id:
            lines.append(f"### 📖 Entry [{ts}] ({key}) [{src_id}]")
        else:
            lines.append(f"### 📖 Entry [{ts}] ({key})")
        lines.append(text)
        lines.append("\n---\n")
    target = chronicle_path(project_id, agent_id)
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return {"project_id": project_id, "agent_id": agent_id, "rows": len(rows), "path": str(target)}
