"""Angelia event API routes."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from api.services import angelia_service

router = APIRouter(prefix="/angelia", tags=["angelia"])


class TickTimerRequest(BaseModel):
    project_id: str | None = None


@router.get("/agents/status")
async def agents_status(project_id: str | None = None):
    return angelia_service.agents_status(project_id=project_id)


@router.post("/timer/tick")
async def tick_timer(req: TickTimerRequest):
    return angelia_service.tick_timer(project_id=req.project_id)


@router.get("/metrics")
async def metrics():
    return angelia_service.metrics()
