"""Angelia event/wakeup API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services import angelia_service

router = APIRouter(prefix="/angelia", tags=["angelia"])


class WakeAgentRequest(BaseModel):
    project_id: str | None = None


class TickTimerRequest(BaseModel):
    project_id: str | None = None


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
