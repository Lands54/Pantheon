"""Angelia event/wakeup API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gods.angelia.models import AngeliaEventState
from gods.angelia.metrics import angelia_metrics
from gods.angelia.scheduler import angelia_supervisor
from gods.angelia.migrate import migrate_to_angelia
from gods.angelia import store
from gods.config import runtime_config

router = APIRouter(prefix="/angelia", tags=["angelia"])


class EnqueueEventRequest(BaseModel):
    project_id: str | None = None
    agent_id: str
    event_type: str
    priority: int | None = None
    payload: dict = Field(default_factory=dict)
    dedupe_key: str = ""


class RetryEventRequest(BaseModel):
    project_id: str | None = None


class WakeAgentRequest(BaseModel):
    project_id: str | None = None


class TickTimerRequest(BaseModel):
    project_id: str | None = None


def _pick_project(project_id: str | None) -> str:
    pid = project_id or runtime_config.current_project
    if pid not in runtime_config.projects:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    return pid


@router.post("/events/enqueue")
async def enqueue_event(req: EnqueueEventRequest) -> dict:
    pid = _pick_project(req.project_id)
    if not str(req.agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    if not str(req.event_type or "").strip():
        raise HTTPException(status_code=400, detail="event_type is required")
    row = angelia_supervisor.enqueue_event(
        project_id=pid,
        agent_id=str(req.agent_id).strip(),
        event_type=str(req.event_type).strip(),
        priority=req.priority,
        payload=req.payload or {},
        dedupe_key=str(req.dedupe_key or ""),
    )
    return {
        "project_id": pid,
        "event_id": row.get("event_id", ""),
        "state": row.get("state", "queued"),
        "queued_at": row.get("created_at", 0.0),
        "event": row,
    }


@router.get("/events")
async def list_events(
    project_id: str | None = None,
    agent_id: str = "",
    state: str = "",
    event_type: str = "",
    limit: int = 100,
):
    pid = _pick_project(project_id)
    st = None
    if state:
        try:
            st = AngeliaEventState(state)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid state: {state}") from e
    rows = store.list_events(
        project_id=pid,
        agent_id=agent_id,
        state=st,
        event_type=event_type,
        limit=max(1, min(limit, 1000)),
    )
    return {"project_id": pid, "items": [r.to_dict() for r in rows]}


@router.post("/events/{event_id}/retry")
async def retry_event(event_id: str, req: RetryEventRequest) -> dict:
    pid = _pick_project(req.project_id)
    ok = store.retry_event(pid, event_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"event '{event_id}' not retryable/not found")
    return {"project_id": pid, "event_id": event_id, "status": "queued"}


@router.get("/agents/status")
async def agents_status(project_id: str | None = None):
    pid = _pick_project(project_id)
    proj = runtime_config.projects.get(pid)
    active = list(getattr(proj, "active_agents", []) or []) if proj else []
    return {
        "project_id": pid,
        "agents": angelia_supervisor.list_agent_status(pid, active),
    }


@router.post("/agents/{agent_id}/wake")
async def wake_agent(agent_id: str, req: WakeAgentRequest):
    pid = _pick_project(req.project_id)
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return angelia_supervisor.wake_agent(pid, agent_id)


@router.post("/timer/tick")
async def tick_timer(req: TickTimerRequest):
    pid = _pick_project(req.project_id)
    return angelia_supervisor.tick_timer_once(pid)


@router.get("/metrics")
async def metrics():
    return {"metrics": angelia_metrics.snapshot()}


@router.post("/migrate")
async def migrate(project_id: str | None = None):
    pid = _pick_project(project_id)
    return migrate_to_angelia(pid)
