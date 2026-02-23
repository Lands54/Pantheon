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


@router.get("/{project_id}/athena/flows")
async def athena_flows(project_id: str):
    """List Athena built-in flow definitions."""
    return project_service.athena_flows(project_id=project_id)


@router.get("/{project_id}/athena/runs")
async def athena_runs(project_id: str, include_inactive: bool = False):
    """List Athena flow runs."""
    return project_service.athena_runs(project_id=project_id, include_inactive=include_inactive)


@router.post("/{project_id}/athena/runs/start")
async def athena_run_start(project_id: str, req: Request):
    """Start one Athena flow run with participant non-overlap guard."""
    data = await req.json()
    return project_service.athena_run_start(
        project_id=project_id,
        flow_key=str(data.get("flow_key", "") or ""),
        participants=list(data.get("participants", []) or []),
        title=str(data.get("title", "") or ""),
        started_by=str(data.get("started_by", "human.overseer") or "human.overseer"),
        config=dict(data.get("config", {}) or {}),
    )


@router.get("/{project_id}/athena/runs/{run_id}")
async def athena_run_get(project_id: str, run_id: str):
    """Get one Athena flow run."""
    return project_service.athena_run_get(project_id=project_id, run_id=run_id)


@router.post("/{project_id}/athena/runs/{run_id}/advance")
async def athena_run_advance(project_id: str, run_id: str, req: Request):
    """Advance one Athena flow run to next stage."""
    data = await req.json()
    return project_service.athena_run_advance(
        project_id=project_id,
        run_id=run_id,
        next_stage=str(data.get("next_stage", "") or ""),
        actor_id=str(data.get("actor_id", "human.overseer") or "human.overseer"),
        note=str(data.get("note", "") or ""),
    )


@router.post("/{project_id}/athena/runs/{run_id}/finish")
async def athena_run_finish(project_id: str, run_id: str, req: Request):
    """Finish/abort/pause one Athena flow run."""
    data = await req.json()
    return project_service.athena_run_finish(
        project_id=project_id,
        run_id=run_id,
        status=str(data.get("status", "completed") or "completed"),
        actor_id=str(data.get("actor_id", "human.overseer") or "human.overseer"),
        note=str(data.get("note", "") or ""),
    )


@router.get("/{project_id}/athena/ledger")
async def athena_ledger(project_id: str, limit: int = 200):
    """Read Athena orchestration ledger."""
    return project_service.athena_ledger(project_id=project_id, limit=limit)


@router.post("/{project_id}/athena/council/start")
async def athena_council_start(project_id: str, req: Request):
    """Start Athena-native council session for a group of agents."""
    data = await req.json()
    return project_service.athena_council_start(
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


@router.post("/{project_id}/athena/council/confirm")
async def athena_council_confirm(project_id: str, req: Request):
    """Confirm one agent for Athena council."""
    data = await req.json()
    return project_service.athena_council_confirm(
        project_id=project_id,
        agent_id=str(data.get("agent_id", "") or ""),
    )


@router.get("/{project_id}/athena/council")
async def athena_council_status(project_id: str):
    """Get Athena council state."""
    return project_service.athena_council_status(project_id=project_id)


@router.post("/{project_id}/athena/council/action")
async def athena_council_action(project_id: str, req: Request):
    """Submit one Athena council action."""
    data = await req.json()
    return project_service.athena_council_action(
        project_id=project_id,
        actor_id=str(data.get("actor_id", "") or ""),
        action_type=str(data.get("action_type", "") or ""),
        payload=dict(data.get("payload", {}) or {}),
    )


@router.post("/{project_id}/athena/council/chair")
async def athena_council_chair(project_id: str, req: Request):
    """Athena council chair actions: pause/resume/terminate/skip_turn."""
    data = await req.json()
    return project_service.athena_council_chair(
        project_id=project_id,
        action=str(data.get("action", "") or ""),
        actor_id=str(data.get("actor_id", "human.overseer") or "human.overseer"),
    )


@router.get("/{project_id}/athena/council/ledger")
async def athena_council_ledger(project_id: str, since_seq: int = 0, limit: int = 200):
    """Read Athena council ledger rows."""
    return project_service.athena_council_ledger(project_id=project_id, since_seq=since_seq, limit=limit)


@router.get("/{project_id}/athena/council/resolutions")
async def athena_council_resolutions(project_id: str, limit: int = 200):
    """Read Athena council resolution rows."""
    return project_service.athena_council_resolutions(project_id=project_id, limit=limit)
