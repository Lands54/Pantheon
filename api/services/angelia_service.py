"""Angelia use-case service."""
from __future__ import annotations

from typing import Any

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.config import runtime_config


class AngeliaService:
    def agents_status(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        proj = runtime_config.projects.get(pid)
        active = list(getattr(proj, "active_agents", []) or []) if proj else []
        return {
            "project_id": pid,
            "agents": angelia_facade.list_agent_status(pid, active),
        }

    def wake_agent(self, agent_id: str, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        if not str(agent_id or "").strip():
            raise HTTPException(status_code=400, detail="agent_id is required")
        return angelia_facade.wake_agent(pid, agent_id)

    def tick_timer(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return angelia_facade.tick_timer_once(pid)

    def metrics(self) -> dict[str, Any]:
        return {"metrics": angelia_facade.metrics_snapshot()}


angelia_service = AngeliaService()
