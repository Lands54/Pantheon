"""
API Routes - Tool Gateway
Expose selected communication tools via stable HTTP endpoints for external agents.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gods.config import runtime_config
from gods.tools.communication import (
    check_inbox,
    send_message,
    list_agents,
    record_protocol,
)


router = APIRouter(prefix="/tool-gateway", tags=["tool-gateway"])


class CheckInboxRequest(BaseModel):
    agent_id: str
    project_id: str | None = None


class SendMessageRequest(BaseModel):
    from_id: str
    to_id: str
    message: str
    project_id: str | None = None


class RecordProtocolRequest(BaseModel):
    subject: str
    topic: str
    relation: str
    object: str
    clause: str
    counterparty: str = ""
    status: str = "agreed"
    project_id: str | None = None


def _pick_project(project_id: str | None) -> str:
    pid = project_id or runtime_config.current_project
    if pid not in runtime_config.projects:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    return pid


@router.get("/list_agents")
async def gw_list_agents(project_id: str | None = None, caller_id: str = "external") -> dict:
    pid = _pick_project(project_id)
    text = list_agents.invoke({"caller_id": caller_id, "project_id": pid})
    return {"project_id": pid, "result": text}


@router.post("/check_inbox")
async def gw_check_inbox(req: CheckInboxRequest) -> dict:
    pid = _pick_project(req.project_id)
    # validate agent exists physically to avoid silent file creation
    agent_dir = Path("projects") / pid / "agents" / req.agent_id
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found in '{pid}'")
    text = check_inbox.invoke({"caller_id": req.agent_id, "project_id": pid})
    parsed = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return {"project_id": pid, "agent_id": req.agent_id, "result": text, "messages": parsed}


@router.post("/send_message")
async def gw_send_message(req: SendMessageRequest) -> dict:
    pid = _pick_project(req.project_id)
    # validate source/target agents exist
    from_dir = Path("projects") / pid / "agents" / req.from_id
    to_dir = Path("projects") / pid / "agents" / req.to_id
    if not from_dir.exists():
        raise HTTPException(status_code=404, detail=f"Sender agent '{req.from_id}' not found in '{pid}'")
    if not to_dir.exists():
        raise HTTPException(status_code=404, detail=f"Target agent '{req.to_id}' not found in '{pid}'")

    text = send_message.invoke(
        {
            "to_id": req.to_id,
            "message": req.message,
            "caller_id": req.from_id,
            "project_id": pid,
        }
    )
    return {"project_id": pid, "from_id": req.from_id, "to_id": req.to_id, "result": text}


@router.post("/record_protocol")
async def gw_record_protocol(req: RecordProtocolRequest) -> dict:
    pid = _pick_project(req.project_id)
    subject_dir = Path("projects") / pid / "agents" / req.subject
    if not subject_dir.exists():
        raise HTTPException(status_code=404, detail=f"Subject agent '{req.subject}' not found in '{pid}'")
    text = record_protocol.invoke(
        {
            "topic": req.topic,
            "relation": req.relation,
            "object": req.object,
            "clause": req.clause,
            "counterparty": req.counterparty,
            "status": req.status,
            "caller_id": req.subject,
            "project_id": pid,
        }
    )
    return {"project_id": pid, "subject": req.subject, "result": text}
