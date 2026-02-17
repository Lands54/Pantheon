"""Unified EventBus API routes."""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

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


@router.get("/catalog")
async def event_catalog(project_id: str | None = None) -> dict:
    return event_service.catalog(project_id=project_id)


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


@router.get("/stream")
async def stream_events(
    project_id: str | None = None,
    domain: str = "",
    event_type: str = "",
    state: str = "",
    agent_id: str = "",
    limit: int = 100,
):
    async def gen():
        last_sig = ""
        last_heartbeat = 0.0
        while True:
            rows = event_service.list(
                project_id=project_id,
                domain=domain,
                event_type=event_type,
                state=state,
                limit=limit,
                agent_id=agent_id,
            )
            items = rows.get("items", [])
            sig = "|".join(
                f"{x.get('event_id','')}:{x.get('state','')}:{x.get('attempt',0)}:{x.get('done_at',0)}:{x.get('error_code','')}"
                for x in items
            )
            now = time.time()
            if sig != last_sig:
                payload = {
                    "type": "snapshot",
                    "project_id": rows.get("project_id", ""),
                    "items": items,
                    "at": now,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_sig = sig
            elif now - last_heartbeat >= 15:
                yield f"event: heartbeat\ndata: {int(now)}\n\n"
                last_heartbeat = now
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")
