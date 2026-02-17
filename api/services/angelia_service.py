"""Angelia use-case service."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.config import runtime_config


class AngeliaService:
    def enqueue_event(
        self,
        project_id: str | None,
        agent_id: str,
        event_type: str,
        payload: dict | None = None,
        priority: int | None = None,
        dedupe_key: str = "",
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        if not str(agent_id or "").strip():
            raise HTTPException(status_code=400, detail="agent_id is required")
        if not str(event_type or "").strip():
            raise HTTPException(status_code=400, detail="event_type is required")
        row = angelia_facade.enqueue_event(
            project_id=pid,
            agent_id=str(agent_id).strip(),
            event_type=str(event_type).strip(),
            payload=payload or {},
            priority=priority,
            dedupe_key=str(dedupe_key or ""),
        )
        return {
            "project_id": pid,
            "event_id": row.get("event_id", ""),
            "state": row.get("state", "queued"),
            "queued_at": row.get("created_at", 0.0),
            "event": row,
        }

    def list_events(
        self,
        project_id: str | None,
        agent_id: str = "",
        state: str = "",
        event_type: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            rows = angelia_facade.list_events(
                project_id=pid,
                agent_id=agent_id,
                state=state,
                event_type=event_type,
                limit=max(1, min(limit, 1000)),
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid state: {state}") from e
        return {"project_id": pid, "items": rows}

    def retry_event(self, event_id: str, project_id: str | None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        ok = angelia_facade.retry_event(pid, event_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not retryable/not found")
        return {"project_id": pid, "event_id": event_id, "status": "queued"}

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

    def migrate(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return angelia_facade.migrate(pid)


angelia_service = AngeliaService()
