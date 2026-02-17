"""Angelia event/wakeup API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services import angelia_service

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


@router.post("/events/enqueue")
async def enqueue_event(req: EnqueueEventRequest) -> dict:
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /events/submit")


@router.get("/events")
async def list_events(
    project_id: str | None = None,
    agent_id: str = "",
    state: str = "",
    event_type: str = "",
    limit: int = 100,
):
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /events")


@router.post("/events/{event_id}/retry")
async def retry_event(event_id: str, req: RetryEventRequest) -> dict:
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /events/{event_id}/retry")


@router.get("/agents/status")
async def agents_status(project_id: str | None = None):
    return angelia_service.agents_status(project_id=project_id)


@router.post("/agents/{agent_id}/wake")
async def wake_agent(agent_id: str, req: WakeAgentRequest):
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return angelia_service.wake_agent(agent_id=agent_id, project_id=req.project_id)


@router.post("/timer/tick")
async def tick_timer(req: TickTimerRequest):
    return angelia_service.tick_timer(project_id=req.project_id)


@router.get("/metrics")
async def metrics():
    return angelia_service.metrics()


@router.post("/migrate")
async def migrate(project_id: str | None = None):
    return angelia_service.migrate(project_id=project_id)
