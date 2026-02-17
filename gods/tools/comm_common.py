"""Shared helpers for communication tools."""
from __future__ import annotations

from gods.paths import agent_dir


def format_comm_error(title: str, reason: str, suggestion: str, caller_id: str, project_id: str) -> str:
    cwd = agent_dir(project_id, caller_id).resolve()
    return (
        f"[Current CWD: {cwd}] "
        f"{title}: {reason}\n"
        f"Suggested next step: {suggestion}"
    )
