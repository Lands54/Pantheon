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


@router.get("/{project_id}/context/llm-latest")
async def get_context_llm_latest(project_id: str, agent_id: str):
    """Get latest full LLM request/response trace row for one agent."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_llm_latest(project_id, str(agent_id).strip())


@router.get("/{project_id}/context/snapshot")
async def get_context_snapshot(project_id: str, agent_id: str, since_intent_seq: int = 0):
    """Get Janus card snapshot (full or incremental delta)."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_snapshot(
        project_id,
        str(agent_id).strip(),
        since_intent_seq=max(0, int(since_intent_seq or 0)),
    )


@router.get("/{project_id}/context/snapshot/compressions")
async def get_context_snapshot_compressions(project_id: str, agent_id: str, limit: int = 50):
    """List Janus snapshot compression records (derived lineage + dropped)."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_snapshot_compressions(
        project_id,
        str(agent_id).strip(),
        limit=max(1, min(int(limit or 50), 500)),
    )


@router.get("/{project_id}/context/snapshot/derived")
async def get_context_snapshot_derived(project_id: str, agent_id: str, limit: int = 100):
    """List Janus derived-card ledger rows (one row per derived card)."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_snapshot_derived(
        project_id,
        str(agent_id).strip(),
        limit=max(1, min(int(limit or 100), 2000)),
    )


@router.get("/{project_id}/context/pulses")
async def get_context_pulses(project_id: str, agent_id: str, from_seq: int = 0, limit: int = 500):
    """List pulse ledger entries and grouped pulses."""
    if not str(agent_id or "").strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    return project_service.context_pulses(
        project_id,
        str(agent_id).strip(),
        from_seq=max(0, int(from_seq or 0)),
        limit=max(1, min(int(limit or 500), 5000)),
    )


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


@router.post("/{project_id}/sync-council/start")
async def sync_council_start(project_id: str, req: Request):
    """Start a synchronous council session for a group of agents."""
    data = await req.json()
    return project_service.sync_council_start(
        project_id=project_id,
        title=str(data.get("title", "") or ""),
        content=str(data.get("content", "") or ""),
        participants=list(data.get("participants", []) or []),
        cycles=int(data.get("cycles", 1) or 1),
        initiator=str(data.get("initiator", "human.overseer") or "human.overseer"),
        rules_profile=str(data.get("rules_profile", "roberts_core_v1") or "roberts_core_v1"),
        agenda=list(data.get("agenda", []) or []),
        timeouts=dict(data.get("timeouts", {}) or {}),
    )


@router.post("/{project_id}/sync-council/confirm")
async def sync_council_confirm(project_id: str, req: Request):
    """Confirm one agent to participate in current synchronous council session."""
    data = await req.json()
    return project_service.sync_council_confirm(
        project_id=project_id,
        agent_id=str(data.get("agent_id", "") or ""),
    )


@router.get("/{project_id}/sync-council")
async def sync_council_status(project_id: str):
    """Get current synchronous council session state."""
    return project_service.sync_council_status(project_id)


@router.post("/{project_id}/sync-council/action")
async def sync_council_action(project_id: str, req: Request):
    """Submit one Robert-rules council action."""
    data = await req.json()
    return project_service.sync_council_action(
        project_id=project_id,
        actor_id=str(data.get("actor_id", "") or ""),
        action_type=str(data.get("action_type", "") or ""),
        payload=dict(data.get("payload", {}) or {}),
    )


@router.post("/{project_id}/sync-council/chair")
async def sync_council_chair(project_id: str, req: Request):
    """Chair override actions: pause/resume/terminate/skip_turn."""
    data = await req.json()
    return project_service.sync_council_chair(
        project_id=project_id,
        action=str(data.get("action", "") or ""),
        actor_id=str(data.get("actor_id", "human.overseer") or "human.overseer"),
    )


@router.get("/{project_id}/sync-council/ledger")
async def sync_council_ledger(project_id: str, since_seq: int = 0, limit: int = 200):
    """Read sync-council ledger rows."""
    return project_service.sync_council_ledger(project_id=project_id, since_seq=since_seq, limit=limit)


@router.get("/{project_id}/sync-council/resolutions")
async def sync_council_resolutions(project_id: str, limit: int = 200):
    """Read sync-council resolution rows."""
    return project_service.sync_council_resolutions(project_id=project_id, limit=limit)
