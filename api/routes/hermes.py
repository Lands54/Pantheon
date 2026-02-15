"""Hermes bus API routes."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gods.config import runtime_config
from gods.hermes import hermes_service
from gods.hermes.errors import HermesError
from gods.hermes.events import hermes_events
from gods.hermes.models import InvokeRequest, ProtocolSpec
from gods.hermes.policy import allow_agent_tool_provider

router = APIRouter(prefix="/hermes", tags=["hermes"])


class RegisterProtocolRequest(BaseModel):
    project_id: str | None = None
    spec: dict


class ContractRegisterRequest(BaseModel):
    project_id: str | None = None
    contract: dict


class ContractCommitRequest(BaseModel):
    project_id: str | None = None
    name: str
    version: str
    agent_id: str


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
    version: str = "1.0.0"
    mode: str = "sync"
    payload: dict = Field(default_factory=dict)


class RouteInvokeRequest(BaseModel):
    project_id: str | None = None
    caller_id: str
    target_agent: str
    function_id: str
    mode: str = "sync"
    payload: dict = Field(default_factory=dict)


def _pick_project(project_id: str | None) -> str:
    pid = project_id or runtime_config.current_project
    if pid not in runtime_config.projects:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    return pid


@router.post("/register")
async def register_protocol(req: RegisterProtocolRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        spec = ProtocolSpec(**req.spec)
        if spec.provider.project_id != pid:
            raise HermesError("HERMES_BAD_REQUEST", "provider.project_id must equal request project_id")
        if spec.provider.type == "agent_tool" and not allow_agent_tool_provider(pid):
            raise HermesError(
                "HERMES_AGENT_TOOL_DISABLED",
                "agent_tool provider is disabled by default for this project. Use http provider or enable hermes_allow_agent_tool_provider.",
            )
        hermes_service.register(pid, spec)
        return {"status": "success", "project_id": pid, "protocol": spec.model_dump()}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
async def list_protocols(project_id: str | None = None) -> dict:
    pid = _pick_project(project_id)
    rows = [s.model_dump() for s in hermes_service.list(pid)]
    return {"project_id": pid, "protocols": rows}


@router.post("/invoke")
async def invoke_protocol(req: InvokeProtocolRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        invoke_req = InvokeRequest(
            project_id=pid,
            caller_id=req.caller_id,
            name=req.name,
            version=req.version,
            mode=req.mode,
            payload=req.payload,
        )
        spec = hermes_service.registry.get(pid, invoke_req.name, invoke_req.version)
        if spec.provider.type == "agent_tool" and not allow_agent_tool_provider(pid):
            raise HermesError(
                "HERMES_AGENT_TOOL_DISABLED",
                "agent_tool provider invocation is disabled for this project.",
            )
        result = hermes_service.invoke(invoke_req)
        return result.model_dump()
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, project_id: str | None = None) -> dict:
    pid = _pick_project(project_id)
    job = hermes_service.get_job(pid, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found in project '{pid}'")
    return {"project_id": pid, "job": job.model_dump()}


@router.get("/invocations")
async def list_invocations(project_id: str | None = None, name: str = "", limit: int = 100) -> dict:
    pid = _pick_project(project_id)
    rows = hermes_service.list_invocations(pid, name=name, limit=limit)
    return {"project_id": pid, "invocations": rows}


@router.post("/route")
async def route_invoke(req: RouteInvokeRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        result = hermes_service.route(
            project_id=pid,
            caller_id=req.caller_id,
            target_agent=req.target_agent,
            function_id=req.function_id,
            payload=req.payload,
            mode=req.mode,
        )
        return result.model_dump()
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts/register")
async def register_contract(req: ContractRegisterRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        payload = hermes_service.contracts.register(pid, req.contract)
        return {"status": "success", "project_id": pid, "contract": payload}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/contracts/commit")
async def commit_contract(req: ContractCommitRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        payload = hermes_service.contracts.commit(pid, req.name, req.version, req.agent_id)
        return {"status": "success", "project_id": pid, "contract": payload}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contracts/list")
async def list_contracts(project_id: str | None = None) -> dict:
    pid = _pick_project(project_id)
    return {"project_id": pid, "contracts": hermes_service.contracts.list(pid)}


@router.get("/contracts/{name}/{version}/resolved")
async def resolve_contract(name: str, version: str, project_id: str | None = None) -> dict:
    pid = _pick_project(project_id)
    try:
        data = hermes_service.contracts.resolve(pid, name, version)
        return {"project_id": pid, "resolved": data}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())


@router.post("/ports/reserve")
async def reserve_port(req: PortReserveRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        lease = hermes_service.ports.reserve(
            project_id=pid,
            owner_id=req.owner_id,
            preferred_port=req.preferred_port,
            min_port=req.min_port,
            max_port=req.max_port,
            note=req.note,
        )
        return {"project_id": pid, "lease": lease}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())


@router.post("/ports/release")
async def release_port(req: PortReleaseRequest) -> dict:
    pid = _pick_project(req.project_id)
    try:
        removed = hermes_service.ports.release(
            project_id=pid,
            owner_id=req.owner_id,
            port=req.port,
        )
        return {"project_id": pid, "released": removed}
    except HermesError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())


@router.get("/ports/list")
async def list_ports(project_id: str | None = None) -> dict:
    pid = _pick_project(project_id)
    return {"project_id": pid, "leases": hermes_service.ports.list(pid)}


@router.get("/events")
async def stream_events(project_id: str | None = None, last_seq: int = 0):
    pid = _pick_project(project_id)

    async def event_gen():
        seq = int(max(0, last_seq))
        while True:
            events = hermes_events.get_since(seq, project_id=pid, limit=200)
            if events:
                for item in events:
                    seq = max(seq, int(item.get("seq", seq)))
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            else:
                yield ": ping\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
