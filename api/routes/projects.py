"""
API Routes - Project Management
Handles /projects endpoints for multi-project operations.
"""
from fastapi import APIRouter, Request
from api.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects():
    """List all projects."""
    return project_service.list_projects()


@router.post("/create")
async def create_project(req: Request):
    """Create a new project."""
    data = await req.json()
    pid = data.get("id")
    return project_service.create_project(pid)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    return project_service.delete_project(project_id)


@router.post("/{project_id}/knowledge/rebuild")
async def rebuild_knowledge_graph(project_id: str):
    """Rebuild project knowledge graph from protocol events."""
    return project_service.rebuild_knowledge(project_id)


@router.post("/{project_id}/start")
async def start_project(project_id: str):
    """
    Start a project's autonomous simulation.
    New active-project paradigm: only one project can run at a time.
    """
    return project_service.start_project(project_id)


@router.post("/{project_id}/stop")
async def stop_project(project_id: str):
    """
    Stop a project's autonomous simulation.
    """
    return project_service.stop_project(project_id)


@router.post("/{project_id}/report/build")
async def build_report(project_id: str):
    """Build project report JSON + Markdown and archive into Mnemosyne human vault."""
    return project_service.build_report(project_id)


@router.get("/{project_id}/report")
async def get_report(project_id: str):
    """Get latest built project report JSON."""
    return project_service.get_report(project_id)
