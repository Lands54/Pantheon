"""
API Routes - Configuration Management
Handles /config endpoints for system configuration.
"""
from fastapi import APIRouter, Request
from gods.config import runtime_config, get_available_agents, ProjectConfig
from gods.tools import GODS_TOOLS

router = APIRouter(prefix="/config", tags=["config"])


def _mask_api_key(raw: str) -> str:
    token = (raw or "").strip()
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{'*' * (len(token) - 4)}{token[-4:]}"


@router.get("")
async def get_config():
    """Get current system configuration."""
    proj = runtime_config.projects.get(runtime_config.current_project)
    if not proj:
        runtime_config.projects["default"] = ProjectConfig()
        proj = runtime_config.projects["default"]

    return {
        "openrouter_api_key": _mask_api_key(runtime_config.openrouter_api_key),
        "has_openrouter_api_key": bool(runtime_config.openrouter_api_key),
        "current_project": runtime_config.current_project,
        "enable_legacy_social_api": runtime_config.enable_legacy_social_api,
        "deprecated": {
            "enable_legacy_social_api": "deprecated-compat",
            "projects.*.autonomous_parallel": "deprecated-noop",
        },
        "projects": runtime_config.projects,
        "available_agents": get_available_agents(),
        "all_tools": [t.name for t in GODS_TOOLS]
    }


@router.post("/save")
async def save_config(req: Request):
    """Save system configuration."""
    data = await req.json()
    if "openrouter_api_key" in data:
        incoming = str(data["openrouter_api_key"] or "")
        # Ignore masked value echo from GET /config to avoid accidental secret overwrite.
        if "*" not in incoming:
            runtime_config.openrouter_api_key = incoming
    if "current_project" in data:
        runtime_config.current_project = data["current_project"]
    if "enable_legacy_social_api" in data:
        runtime_config.enable_legacy_social_api = bool(data["enable_legacy_social_api"])
    if "projects" in data:
        for pid, pdata in data["projects"].items():
            runtime_config.projects[pid] = ProjectConfig(**pdata)
    
    runtime_config.save()
    return {"status": "success"}
