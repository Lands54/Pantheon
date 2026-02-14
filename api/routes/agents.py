"""
API Routes - Agent Management
Handles /agents endpoints for agent creation and deletion.
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from gods.config import runtime_config, AgentModelConfig
from api.models import CreateAgentRequest

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/create")
async def create_agent(req: CreateAgentRequest):
    """Create a new agent in the current project."""
    project_id = runtime_config.current_project
    agent_dir = Path("projects") / project_id / "agents" / req.agent_id
    if agent_dir.exists():
        raise HTTPException(status_code=400, detail="Agent exists")
    
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.md").write_text(req.directives, encoding="utf-8")
    
    proj = runtime_config.projects[project_id]
    if req.agent_id not in proj.agent_settings:
        proj.agent_settings[req.agent_id] = AgentModelConfig()
    runtime_config.save()
    return {"status": "success"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent from the current project."""
    project_id = runtime_config.current_project
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    if not agent_dir.exists():
        raise HTTPException(status_code=404)
    
    shutil.rmtree(agent_dir)
    proj = runtime_config.projects[project_id]
    if agent_id in proj.active_agents:
        proj.active_agents.remove(agent_id)
    if agent_id in proj.agent_settings:
        del proj.agent_settings[agent_id]
    runtime_config.save()
    return {"status": "success"}
