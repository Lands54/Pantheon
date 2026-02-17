"""
API Routes - Tool Gateway
Expose selected communication tools via stable HTTP endpoints for external agents.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from api.services import tool_gateway_service


router = APIRouter(prefix="/tool-gateway", tags=["tool-gateway"])


class CheckInboxRequest(BaseModel):
    agent_id: str
    project_id: str | None = None


class SendMessageRequest(BaseModel):
    from_id: str
    to_id: str
    title: str = ""
    message: str
    project_id: str | None = None


class CheckOutboxRequest(BaseModel):
    agent_id: str
    project_id: str | None = None
    to_id: str = ""
    status: str = ""
    limit: int = 50


@router.get("/list_agents")
async def gw_list_agents(project_id: str | None = None, caller_id: str = "external") -> dict:
    return tool_gateway_service.list_agents(project_id=project_id, caller_id=caller_id)


@router.post("/check_inbox")
async def gw_check_inbox(req: CheckInboxRequest) -> dict:
    return tool_gateway_service.check_inbox(project_id=req.project_id, agent_id=req.agent_id)


@router.post("/check_outbox")
async def gw_check_outbox(req: CheckOutboxRequest) -> dict:
    return tool_gateway_service.check_outbox(
        project_id=req.project_id,
        agent_id=req.agent_id,
        to_id=req.to_id,
        status=req.status,
        limit=int(req.limit),
    )


@router.post("/send_message")
async def gw_send_message(req: SendMessageRequest) -> dict:
    return tool_gateway_service.send_message(
        project_id=req.project_id,
        from_id=req.from_id,
        to_id=req.to_id,
        title=req.title,
        message=req.message,
    )
