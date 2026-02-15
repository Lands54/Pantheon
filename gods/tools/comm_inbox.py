"""Inbox-related communication tools."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path

from langchain.tools import tool

from gods.tools.comm_common import format_comm_error


def _inbox_guard_path(caller_id: str, project_id: str) -> Path:
    project_root = Path(__file__).parent.parent.parent.absolute()
    guard_dir = project_root / "projects" / project_id / "buffers"
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
    """Check your own divine inbox for private revelations in the current project."""
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

        project_root = Path(__file__).parent.parent.parent.absolute()
        buffer_dir = project_root / "projects" / project_id / "buffers"
        buffer_path = buffer_dir / f"{caller_id}.jsonl"

        if not buffer_path.exists():
            if not guard.get("warned_empty", False):
                _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": False})
                return (
                    "Inbox Empty Warning: no new messages. "
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

        messages = []
        read_path = buffer_dir / f"{caller_id}_read.jsonl"
        read_timestamp = time.time()

        with open(buffer_path, "r+", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                for line in f:
                    if line.strip():
                        msg = json.loads(line)
                        msg["read_at"] = read_timestamp
                        messages.append(msg)

                if messages:
                    with open(read_path, "a", encoding="utf-8") as rf:
                        fcntl.flock(rf, fcntl.LOCK_EX)
                        for m in messages:
                            rf.write(json.dumps(m, ensure_ascii=False) + "\n")
                        fcntl.flock(rf, fcntl.LOCK_UN)

                f.seek(0)
                f.truncate()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        if messages:
            reset_inbox_guard(caller_id, project_id)
        else:
            if not guard.get("warned_empty", False):
                _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": False})
                return (
                    "Inbox Empty Warning: no new messages. "
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

        return json.dumps(messages, ensure_ascii=False)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry inbox check; if it persists, verify buffer file permissions.",
            caller_id,
            project_id,
        )
