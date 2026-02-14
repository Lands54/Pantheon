"""
API Routes - Configuration Management
Handles /config endpoints for system configuration.
"""
from fastapi import APIRouter, Request
from gods.config import runtime_config, get_available_agents, ProjectConfig
from gods.tools import GODS_TOOLS

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    """Get current system configuration."""
    proj = runtime_config.projects.get(runtime_config.current_project)
    if not proj:
        runtime_config.projects["default"] = ProjectConfig()
        proj = runtime_config.projects["default"]

    return {
        "openrouter_api_key": runtime_config.openrouter_api_key,
        "current_project": runtime_config.current_project,
        "projects": runtime_config.projects,
        "available_agents": get_available_agents(),
        "all_tools": [t.name for t in GODS_TOOLS]
    }


@router.post("/save")
async def save_config(req: Request):
    """Save system configuration."""
    data = await req.json()
    if "openrouter_api_key" in data:
        runtime_config.openrouter_api_key = data["openrouter_api_key"]
    if "current_project" in data:
        runtime_config.current_project = data["current_project"]
    if "projects" in data:
        for pid, pdata in data["projects"].items():
            runtime_config.projects[pid] = ProjectConfig(**pdata)
    
    runtime_config.save()
    return {"status": "success"}
