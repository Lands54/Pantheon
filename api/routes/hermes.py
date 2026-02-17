"""Hermes bus API routes."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services import hermes_service

router = APIRouter(prefix="/hermes", tags=["hermes"])


class RegisterProtocolRequest(BaseModel):
    project_id: str | None = None
    spec: dict


class ContractRegisterRequest(BaseModel):
    project_id: str | None = None
    contract: dict


class ContractCommitRequest(BaseModel):
    project_id: str | None = None
    title: str
    version: str
    agent_id: str


class ContractDisableRequest(BaseModel):
    project_id: str | None = None
    title: str
    version: str
    agent_id: str
    reason: str = ""


class PortReserveRequest(BaseModel):
    project_id: str | None = None
    owner_id: str
    preferred_port: int | None = None
    min_port: int = 12000
    max_port: int = 19999
    note: str = ""


class PortReleaseRequest(BaseModel):
    project_id: str | None = None
    owner_id: str
    port: int | None = None


class InvokeProtocolRequest(BaseModel):
    project_id: str | None = None
    caller_id: str
    name: str
    mode: str = "sync"
    payload: dict = Field(default_factory=dict)


class RouteInvokeRequest(BaseModel):
    project_id: str | None = None
    caller_id: str
    target_agent: str
    function_id: str
    mode: str = "sync"
    payload: dict = Field(default_factory=dict)


@router.post("/register")
async def register_protocol(req: RegisterProtocolRequest) -> dict:
    return hermes_service.register_protocol(project_id=req.project_id, spec_payload=req.spec)


@router.get("/list")
async def list_protocols(project_id: str | None = None) -> dict:
    return hermes_service.list_protocols(project_id=project_id)


@router.post("/invoke")
async def invoke_protocol(req: InvokeProtocolRequest) -> dict:
    return hermes_service.invoke(
        project_id=req.project_id,
        caller_id=req.caller_id,
        name=req.name,
        mode=req.mode,
        payload=req.payload,
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, project_id: str | None = None) -> dict:
    return hermes_service.get_job(job_id=job_id, project_id=project_id)


@router.get("/invocations")
async def list_invocations(project_id: str | None = None, name: str = "", limit: int = 100) -> dict:
    return hermes_service.list_invocations(project_id=project_id, name=name, limit=limit)


@router.post("/route")
async def route_invoke(req: RouteInvokeRequest) -> dict:
    return hermes_service.route_invoke(
        project_id=req.project_id,
        caller_id=req.caller_id,
        target_agent=req.target_agent,
        function_id=req.function_id,
        mode=req.mode,
        payload=req.payload,
    )


@router.post("/contracts/register")
async def register_contract(req: ContractRegisterRequest) -> dict:
    return hermes_service.register_contract(project_id=req.project_id, contract=req.contract)


@router.post("/contracts/commit")
async def commit_contract(req: ContractCommitRequest) -> dict:
    return hermes_service.commit_contract(
        project_id=req.project_id,
        title=req.title,
        version=req.version,
        agent_id=req.agent_id,
    )


@router.get("/contracts/list")
async def list_contracts(project_id: str | None = None, include_disabled: bool = False) -> dict:
    return hermes_service.list_contracts(project_id=project_id, include_disabled=include_disabled)


@router.post("/contracts/disable")
async def disable_contract(req: ContractDisableRequest) -> dict:
    return hermes_service.disable_contract(
        project_id=req.project_id,
        title=req.title,
        version=req.version,
        agent_id=req.agent_id,
        reason=req.reason,
    )


@router.post("/ports/reserve")
async def reserve_port(req: PortReserveRequest) -> dict:
    return hermes_service.reserve_port(
        project_id=req.project_id,
        owner_id=req.owner_id,
        preferred_port=req.preferred_port,
        min_port=req.min_port,
        max_port=req.max_port,
        note=req.note,
    )


@router.post("/ports/release")
async def release_port(req: PortReleaseRequest) -> dict:
    return hermes_service.release_port(project_id=req.project_id, owner_id=req.owner_id, port=req.port)


@router.get("/ports/list")
async def list_ports(project_id: str | None = None) -> dict:
    return hermes_service.list_ports(project_id=project_id)


@router.get("/events")
async def stream_events(project_id: str | None = None, last_seq: int = 0):
    async def event_gen():
        seq = int(max(0, last_seq))
        while True:
            events = hermes_service.events_since(project_id=project_id, seq=seq, limit=200)
            if events:
                for item in events:
                    seq = max(seq, int(item.get("seq", seq)))
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\\n\\n"
            else:
                yield ": ping\\n\\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
