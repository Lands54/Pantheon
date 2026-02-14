"""
API Routes - Project Management
Handles /projects endpoints for multi-project operations.
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from gods.config import runtime_config, ProjectConfig
from gods.protocols import build_knowledge_graph

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects():
    """List all projects."""
    return {"projects": runtime_config.projects, "current": runtime_config.current_project}


@router.post("/create")
async def create_project(req: Request):
    """Create a new project."""
    data = await req.json()
    pid = data.get("id")
    if pid in runtime_config.projects:
        return {"error": "Project exists"}
    
    runtime_config.projects[pid] = ProjectConfig()
    runtime_config.save()
    
    # Initialize basic structure
    agent_dir = Path("projects") / pid / "agents" / "genesis"
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_md = agent_dir / "agent.md"
    if not agent_md.exists():
        agent_md.write_text(
            "# GENESIS\nYou are the first Being of this new world. Observe, evolve, and manifest.",
            encoding="utf-8"
        )
        
    return {"status": "success"}


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    if project_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default world")
    if project_id not in runtime_config.projects:
        raise HTTPException(status_code=404)
    
    # Remove from config
    del runtime_config.projects[project_id]
    if runtime_config.current_project == project_id:
        runtime_config.current_project = "default"
    runtime_config.save()
    
    # Remove from disk
    proj_dir = Path("projects") / project_id
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
        
    return {"status": "success"}


@router.post("/{project_id}/knowledge/rebuild")
async def rebuild_knowledge_graph(project_id: str):
    """Rebuild project knowledge graph from protocol events."""
    if project_id not in runtime_config.projects:
        raise HTTPException(status_code=404, detail="Project not found")
    graph = build_knowledge_graph(project_id)
    return {
        "status": "success",
        "project_id": project_id,
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "output": f"projects/{project_id}/knowledge/knowledge_graph.json",
    }


@router.post("/{project_id}/start")
async def start_project(project_id: str):
    """
    Start a project's autonomous simulation.
    New active-project paradigm: only one project can run at a time.
    """
    if project_id not in runtime_config.projects:
        raise HTTPException(status_code=404, detail="Project not found")

    # Pause all projects first to enforce single active project runtime.
    for pid, proj in runtime_config.projects.items():
        proj.simulation_enabled = (pid == project_id)

    runtime_config.current_project = project_id
    runtime_config.save()
    return {
        "status": "success",
        "project_id": project_id,
        "simulation_enabled": True,
        "current_project": runtime_config.current_project,
    }


@router.post("/{project_id}/stop")
async def stop_project(project_id: str):
    """
    Stop a project's autonomous simulation.
    """
    if project_id not in runtime_config.projects:
        raise HTTPException(status_code=404, detail="Project not found")

    runtime_config.projects[project_id].simulation_enabled = False
    runtime_config.save()
    return {
        "status": "success",
        "project_id": project_id,
        "simulation_enabled": False,
        "current_project": runtime_config.current_project,
    }
