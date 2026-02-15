"""Inbox-related communication tools."""
from __future__ import annotations

import json
from pathlib import Path

from langchain.tools import tool

from gods.inbox import ack_handled
from gods.inbox.store import take_deliverable_inbox_events
from gods.tools.comm_common import format_comm_error


def _inbox_guard_path(caller_id: str, project_id: str) -> Path:
    project_root = Path(__file__).parent.parent.parent.absolute()
    guard_dir = project_root / "projects" / project_id / "runtime"
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / f"{caller_id}_inbox_guard.json"


def _load_inbox_guard(caller_id: str, project_id: str) -> dict:
    path = _inbox_guard_path(caller_id, project_id)
    if not path.exists():
        return {"warned_empty": False, "blocked": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"warned_empty": False, "blocked": False}


def _save_inbox_guard(caller_id: str, project_id: str, state: dict):
    path = _inbox_guard_path(caller_id, project_id)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def reset_inbox_guard(caller_id: str, project_id: str):
    """Called by non-inbox actions: allow future inbox checks again."""
    _save_inbox_guard(caller_id, project_id, {"warned_empty": False, "blocked": False})


@tool
def check_inbox(caller_id: str, project_id: str = "default") -> str:
    """Check your own inbox events (debug/audit fallback; normally pre-injected by pulse runtime)."""
    try:
        guard = _load_inbox_guard(caller_id, project_id)
        if guard.get("blocked"):
            return (
                format_comm_error(
                    "Divine Warning",
                    "Inbox checks are temporarily blocked after repeated empty checks.",
                    "Perform one non-inbox action (read/write/list/run/send), then check inbox again.",
                    caller_id,
                    project_id,
                )
            )

        events = take_deliverable_inbox_events(project_id=project_id, agent_id=caller_id, budget=50)
        if not events:
            if not guard.get("warned_empty", False):
                _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": False})
                return (
                    "Inbox Empty Warning: no new event messages. "
                    "If you check again without doing other work, inbox checks will be blocked once."
                )
            _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": True})
            return (
                format_comm_error(
                    "Divine Warning",
                    "Inbox is still empty and now temporarily blocked.",
                    "Do one non-inbox action first, then check again.",
                    caller_id,
                    project_id,
                )
            )

        event_ids = [item.event_id for item in events]
        ack_handled(project_id, event_ids)
        reset_inbox_guard(caller_id, project_id)
        payload = [item.to_dict() for item in events]
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry inbox check; if it persists, verify runtime event file permissions.",
            caller_id,
            project_id,
        )
