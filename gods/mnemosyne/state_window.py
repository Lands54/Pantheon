"""Persistent cross-pulse state window store (Mnemosyne-owned)."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict

from gods.config import runtime_config
from gods.paths import runtime_state_window_path


def _state_window_path(project_id: str, agent_id: str):
    p = runtime_state_window_path(project_id, agent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _state_window_limit(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "context_state_window_limit", 50) if proj else 50)
    return max(1, min(value, 500))


def load_state_window(project_id: str, agent_id: str) -> list[Any]:
    p = _state_window_path(project_id, agent_id)
    if not p.exists():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        rows = obj.get("messages", []) if isinstance(obj, dict) else []
        if not isinstance(rows, list):
            return []
        msgs = messages_from_dict(rows)
        return list(msgs or [])
    except Exception:
        return []


def save_state_window(project_id: str, agent_id: str, messages: list[Any]):
    limit = _state_window_limit(project_id)
    tail = list(messages or [])[-limit:]
    payload = {
        "project_id": project_id,
        "agent_id": agent_id,
        "limit": limit,
        "messages": messages_to_dict(tail),
    }
    p = _state_window_path(project_id, agent_id)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

