"""
API Routes - Project Management
Handles /projects endpoints for multi-project operations.
"""
from fastapi import APIRouter, HTTPException, Request
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


@router.get("/{project_id}/context/preview")
async def get_context_preview(project_id: str, agent_id: str):
    """Get latest Janus context build preview for one agent."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_preview(project_id, str(agent_id).strip())


@router.get("/{project_id}/context/reports")
async def get_context_reports(project_id: str, agent_id: str, limit: int = 20):
    """List Janus context build reports for one agent."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_reports(project_id, str(agent_id).strip(), limit=max(1, min(limit, 500)))


@router.get("/{project_id}/inbox/outbox")
async def get_outbox_receipts(
    project_id: str,
    from_agent_id: str = "",
    to_agent_id: str = "",
    status: str = "",
    limit: int = 100,
):
    """Inspect outbox receipts for sender-side message status."""
    return project_service.outbox_receipts(
        project_id=project_id,
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        status=status,
        limit=max(1, min(limit, 500)),
    )


@router.get("/{project_id}/runtime/agents")
async def runtime_agents_status(project_id: str):
    """List runtime container status for active agents in project."""
    return project_service.runtime_status(project_id)


@router.post("/{project_id}/runtime/agents/{agent_id}/restart")
async def runtime_restart_agent(project_id: str, agent_id: str):
    """Restart one active agent runtime container."""
    return project_service.runtime_restart_agent(project_id, agent_id)


@router.post("/{project_id}/runtime/reconcile")
async def runtime_reconcile(project_id: str):
    """Reconcile runtime containers against project's active_agents list."""
    return project_service.runtime_reconcile(project_id)


@router.post("/{project_id}/detach/submit")
async def detach_submit(project_id: str, req: Request):
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /events/submit with runtime detach event")


@router.get("/{project_id}/detach/jobs")
async def detach_jobs(project_id: str, agent_id: str = "", status: str = "", limit: int = 50):
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /events?domain=runtime")


@router.post("/{project_id}/detach/jobs/{job_id}/stop")
async def detach_stop(project_id: str, job_id: str):
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /events/submit detach_stopping_event")


@router.post("/{project_id}/detach/reconcile")
async def detach_reconcile(project_id: str):
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /events/reconcile")


@router.get("/{project_id}/detach/jobs/{job_id}/logs")
async def detach_logs(project_id: str, job_id: str):
    raise HTTPException(status_code=410, detail="Deprecated. Use runtime logs via events domain tools")
