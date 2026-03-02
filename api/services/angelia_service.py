"""Angelia use-case service."""
from __future__ import annotations

from typing import Any

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.agents import registry as agent_registry


class AngeliaService:
    def agents_status(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        active = agent_registry.list_active_agents(pid)
        return {
            "project_id": pid,
            "agents": angelia_facade.list_agent_status(pid, active),
        }

    def tick_timer(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return angelia_facade.tick_timer_once(pid)

    def metrics(self) -> dict[str, Any]:
        return {"metrics": angelia_facade.metrics_snapshot()}


angelia_service = AngeliaService()
