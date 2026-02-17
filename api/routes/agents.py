"""
API Routes - Agent Management
Handles /agents endpoints for agent creation and deletion.
"""
import asyncio
import json
import time

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from api.services import agent_service
from api.models import CreateAgentRequest

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status")
async def get_agents_status(project_id: str = None):
    """Get scheduler status for active agents in selected project."""
    return agent_service.status(project_id=project_id)


@router.post("/create")
async def create_agent(req: CreateAgentRequest):
    """Create a new agent in the current project."""
    return agent_service.create(agent_id=req.agent_id, directives=req.directives)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent from the current project."""
    return agent_service.delete(agent_id=agent_id)


@router.get("/status/stream")
async def stream_agents_status(project_id: str = None):
    async def gen():
        last_sig = ""
        last_heartbeat = 0.0
        while True:
            rows = agent_service.status(project_id=project_id)
            agents = rows.get("agents", [])
            sig = "|".join(
                f"{x.get('agent_id','')}:{x.get('status','')}:{x.get('queued_pulse_events',0)}:{int(x.get('has_pending_inbox', False))}:{x.get('last_error','')}"
                for x in agents
            )
            now = time.time()
            if sig != last_sig:
                payload = {
                    "type": "snapshot",
                    "project_id": rows.get("project_id", ""),
                    "agents": agents,
                    "at": now,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_sig = sig
            elif now - last_heartbeat >= 15:
                yield f"event: heartbeat\ndata: {int(now)}\n\n"
                last_heartbeat = now
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")
