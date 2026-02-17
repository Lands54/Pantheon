"""Shared helpers for API service project resolution."""
from __future__ import annotations

from fastapi import HTTPException

from gods.config import runtime_config


def resolve_project(project_id: str | None) -> str:
    pid = str(project_id or runtime_config.current_project).strip()
    if pid not in runtime_config.projects:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    return pid
