"""
API Routes - Agent Management
Handles /agents endpoints for agent creation and deletion.
"""
from fastapi import APIRouter
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
