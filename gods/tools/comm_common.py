"""Shared helpers for communication tools."""
from __future__ import annotations

from pathlib import Path


def format_comm_error(title: str, reason: str, suggestion: str, caller_id: str, project_id: str) -> str:
    project_root = Path(__file__).parent.parent.parent.absolute()
    cwd = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
    return (
        f"[Current CWD: {cwd}] "
        f"{title}: {reason}\n"
        f"Suggested next step: {suggestion}"
    )
