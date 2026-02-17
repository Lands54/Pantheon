"""Inbox-related communication tools."""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.tools import tool

from gods.iris.facade import ack_handled, fetch_inbox_context, list_outbox_receipts
from gods.paths import runtime_dir
from gods.tools.comm_common import format_comm_error


def _inbox_guard_path(caller_id: str, project_id: str) -> Path:
    guard_dir = runtime_dir(project_id)
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

        text, event_ids = fetch_inbox_context(project_id=project_id, agent_id=caller_id, budget=50)
        if not event_ids:
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

        ack_handled(project_id, event_ids, caller_id)
        reset_inbox_guard(caller_id, project_id)
        events = []
        pat = re.compile(
            r"^- \[title=(?P<title>.*?)\]\[from=(?P<sender>.*?)\]\[status=(?P<status>.*?)\] at=(?P<at>[-0-9.]+) id=(?P<eid>[a-zA-Z0-9]+): (?P<content>.*)$"
        )
        for line in str(text or "").splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            events.append(
                {
                    "id": m.group("eid"),
                    "title": m.group("title"),
                    "from": m.group("sender"),
                    "to": caller_id,
                    "status": m.group("status"),
                    "type": "private",
                    "content": m.group("content"),
                    "created_at": float(m.group("at") or 0.0),
                }
            )
        payload = [
            x for x in events if str(x.get("id", "")) in set(event_ids)
        ]
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry inbox check; if it persists, verify runtime event file permissions.",
            caller_id,
            project_id,
        )


@tool
def check_outbox(
    caller_id: str,
    project_id: str = "default",
    to_id: str = "",
    status: str = "",
    limit: int = 50,
) -> str:
    """Check my sent-message receipts with [title][to][status] facts."""
    try:
        rows = list_outbox_receipts(
            project_id=project_id,
            from_agent_id=caller_id,
            to_agent_id=str(to_id or "").strip(),
            status=str(status or "").strip(),
            limit=max(1, min(int(limit), 200)),
        )
        payload = [
            {
                "id": r.receipt_id,
                "title": r.title,
                "to": r.to_agent_id,
                "status": r.status.value,
                "message_id": r.message_id,
                "updated_at": r.updated_at,
                "error": r.error_message,
            }
            for r in rows
        ]
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry check_outbox; if it persists, verify runtime receipt files.",
            caller_id,
            project_id,
        )
