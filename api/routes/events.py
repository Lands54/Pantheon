"""Unified EventBus API routes."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services.event_service import event_service

router = APIRouter(prefix="/events", tags=["events"])


class SubmitEventRequest(BaseModel):
    project_id: str | None = None
    domain: str
    event_type: str
    priority: int | None = None
    payload: dict = Field(default_factory=dict)
    dedupe_key: str = ""
    max_attempts: int = 3


class RetryEventRequest(BaseModel):
    project_id: str | None = None


class AckEventRequest(BaseModel):
    project_id: str | None = None


class ReconcileRequest(BaseModel):
    project_id: str | None = None
    timeout_sec: int = 60


@router.post("/submit")
async def submit_event(req: SubmitEventRequest) -> dict:
    return event_service.submit(
        project_id=req.project_id,
        domain=req.domain,
        event_type=req.event_type,
        payload=req.payload,
        priority=req.priority,
        dedupe_key=req.dedupe_key,
        max_attempts=req.max_attempts,
    )


@router.get("")
async def list_events(
    project_id: str | None = None,
    domain: str = "",
    event_type: str = "",
    state: str = "",
    agent_id: str = "",
    limit: int = 100,
) -> dict:
    return event_service.list(
        project_id=project_id,
        domain=domain,
        event_type=event_type,
        state=state,
        limit=limit,
        agent_id=agent_id,
    )


@router.post("/{event_id}/retry")
async def retry_event(event_id: str, req: RetryEventRequest) -> dict:
    return event_service.retry(project_id=req.project_id, event_id=event_id)


@router.post("/{event_id}/ack")
async def ack_event(event_id: str, req: AckEventRequest) -> dict:
    return event_service.ack(project_id=req.project_id, event_id=event_id)


@router.post("/reconcile")
async def reconcile(req: ReconcileRequest) -> dict:
    return event_service.reconcile(project_id=req.project_id, timeout_sec=req.timeout_sec)


@router.get("/metrics")
async def metrics(project_id: str | None = None) -> dict:
    return event_service.metrics(project_id=project_id)
