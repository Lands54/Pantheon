"""
API Routes - Project Management
Handles /projects endpoints for multi-project operations.
"""
from fastapi import APIRouter, HTTPException, Request
from api.services import project_service
from api.scheduler import push_manual_pulse
from gods.inbox import InboxMessageState, list_events
from gods.pulse import PulseEventStatus, list_pulse_events

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


@router.get("/{project_id}/pulse/queue")
async def get_pulse_queue(project_id: str, agent_id: str = "", status: str = "queued", limit: int = 100):
    """Inspect project pulse queue events (debug)."""
    project_service.ensure_exists(project_id)
    st = None
    if status:
        try:
            st = PulseEventStatus(status)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from e
    rows = list_pulse_events(
        project_id=project_id,
        agent_id=(agent_id or None),
        status=st,
        limit=max(1, min(limit, 500)),
    )
    return {"project_id": project_id, "items": [r.to_dict() for r in rows]}


@router.post("/{project_id}/pulse/enqueue")
async def enqueue_pulse(project_id: str, req: Request):
    """Push manual/system pulse event to queue."""
    project_service.ensure_exists(project_id)
    data = await req.json()
    agent_id = str(data.get("agent_id", "")).strip()
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    event_type = str(data.get("event_type", "manual")).strip() or "manual"
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    return push_manual_pulse(project_id, agent_id, event_type=event_type, payload=payload)


@router.get("/{project_id}/inbox/events")
async def get_inbox_events(project_id: str, agent_id: str = "", state: str = "", limit: int = 100):
    """Inspect project inbox events (debug)."""
    project_service.ensure_exists(project_id)
    st = None
    if state:
        try:
            st = InboxMessageState(state)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid state: {state}") from e
    rows = list_events(
        project_id=project_id,
        agent_id=(agent_id or None),
        state=st,
        limit=max(1, min(limit, 500)),
    )
    return {"project_id": project_id, "items": [r.to_dict() for r in rows]}
