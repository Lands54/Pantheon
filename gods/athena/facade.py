"""Athena top-level process orchestrator.

Athena manages project-level, agent-external flow runs and guarantees that
active runs do not overlap on participants.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from gods.athena.models import FlowDefinition, FlowRun
from gods.athena import store


_BUILTIN_DEFS: dict[str, FlowDefinition] = {
    "explore_contract_loop": FlowDefinition(
        key="explore_contract_loop",
        title="Explore & Contract Loop",
        stages=["explore", "converge", "contract", "execute", "review"],
        description="General loop: broad negotiation -> contract convergence -> execution -> review.",
    ),
    "roberts_council": FlowDefinition(
        key="roberts_council",
        title="Robert Council Process",
        stages=["collecting", "draining", "in_session", "completed"],
        description="Structured council session process coordinated by Robert Rules.",
    ),
}

_ACTIVE_STATES = {"active", "paused"}


def _is_roberts_flow(run_or_key: FlowRun | str) -> bool:
    if isinstance(run_or_key, FlowRun):
        return str(run_or_key.flow_key or "") == "roberts_council"
    return str(run_or_key or "") == "roberts_council"


def _sync_run_from_roberts(project_id: str, run: FlowRun) -> FlowRun:
    if not _is_roberts_flow(run):
        return run
    try:
        from gods.athena import council_engine

        state = dict(council_engine.get_state(project_id) or {})
    except Exception:
        return run
    if not state:
        return run
    roberts_session_id = str((run.config or {}).get("roberts_session_id", "") or "")
    current_session_id = str(state.get("session_id", "") or "")
    if roberts_session_id and current_session_id and roberts_session_id != current_session_id:
        return run
    phase = str(state.get("phase", "") or "").strip()
    if phase in set(run.stages or []):
        run.stage_index = max(0, run.stages.index(phase))
    if phase == "paused":
        run.status = "paused"
    elif phase == "aborted":
        run.status = "aborted"
    elif phase == "completed":
        run.status = "completed"
    else:
        run.status = "active"
    if current_session_id:
        cfg = dict(run.config or {})
        cfg["roberts_session_id"] = current_session_id
        run.config = cfg
    run.updated_at = float(time.time())
    return run


def _patch_run(project_id: str, run_id: str, mutator) -> dict[str, Any]:
    def _mut(rows_raw: list[dict[str, Any]]):
        rows = [FlowRun.from_dict(x) for x in rows_raw]
        run = _find_run(rows, run_id)
        if not run:
            raise ValueError("run not found")
        mutator(run)
        run.updated_at = float(time.time())
        return [x.to_dict() for x in rows], run.to_dict()

    return store.with_lock(project_id, _mut)


def list_flow_definitions() -> list[dict[str, Any]]:
    return [x.to_dict() for x in _BUILTIN_DEFS.values()]


def _clean_participants(participants: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in list(participants or []):
        aid = str(raw or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return out


def _resolve_stages(flow_key: str, config: dict[str, Any]) -> list[str]:
    if flow_key in _BUILTIN_DEFS:
        return list(_BUILTIN_DEFS[flow_key].stages)
    stages = [str(x).strip() for x in list((config or {}).get("stages", []) or []) if str(x).strip()]
    uniq: list[str] = []
    for s in stages:
        if s not in uniq:
            uniq.append(s)
    if len(uniq) < 2:
        raise ValueError("custom flow requires at least 2 non-empty stages")
    return uniq


def _find_run(rows: list[FlowRun], run_id: str) -> FlowRun | None:
    rid = str(run_id or "").strip()
    for r in rows:
        if r.run_id == rid:
            return r
    return None


def start_flow_run(
    project_id: str,
    *,
    flow_key: str,
    participants: list[str],
    title: str = "",
    started_by: str = "human.overseer",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fk = str(flow_key or "").strip()
    if not fk:
        raise ValueError("flow_key is required")
    members = _clean_participants(participants)
    if not members:
        raise ValueError("participants is required")
    cfg = dict(config or {})
    stages = _resolve_stages(fk, cfg)

    now = float(time.time())
    rid = f"athena_{uuid.uuid4().hex[:12]}"

    def _mut(rows_raw: list[dict[str, Any]]):
        rows = [FlowRun.from_dict(x) for x in rows_raw]
        target = set(members)
        conflicts: list[dict[str, Any]] = []
        for row in rows:
            if row.status not in _ACTIVE_STATES:
                continue
            inter = sorted(target.intersection(set(row.participants)))
            if inter:
                conflicts.append({"run_id": row.run_id, "participants": inter})
        # Robert council engine is singleton per project; keep one active run.
        if fk == "roberts_council":
            for row in rows:
                if row.status in _ACTIVE_STATES and _is_roberts_flow(row):
                    conflicts.append({"run_id": row.run_id, "participants": list(row.participants or [])})
        if conflicts:
            raise ValueError(f"participants overlap with active flow(s): {conflicts}")

        run = FlowRun(
            run_id=rid,
            project_id=str(project_id),
            flow_key=fk,
            title=str(title or fk),
            participants=members,
            status="active",
            stages=stages,
            stage_index=0,
            config=cfg,
            created_at=now,
            updated_at=now,
            started_by=str(started_by or "human.overseer"),
        )
        rows.append(run)
        store.append_ledger(
            project_id,
            {
                "kind": "flow.start",
                "run_id": run.run_id,
                "flow_key": run.flow_key,
                "participants": list(run.participants),
                "stage": run.current_stage,
                "actor_id": run.started_by,
            },
        )
        return [x.to_dict() for x in rows], run.to_dict()

    run = store.with_lock(project_id, _mut)
    # External engine hookup: Robert session is created by Athena start.
    if fk == "roberts_council":
        try:
            from gods.athena import council_engine

            rp = council_engine.start_session(
                project_id,
                title=str(title or fk),
                content=str(cfg.get("content", "") or ""),
                participants=members,
                cycles=max(1, int(cfg.get("cycles", 1) or 1)),
                initiator=str(started_by or "human.overseer"),
                rules_profile=str(cfg.get("rules_profile", "roberts_core_v1") or "roberts_core_v1"),
                agenda=list(cfg.get("agenda", []) or []),
                timeouts=dict(cfg.get("timeouts", {}) or {}),
            )
            sid = str((rp or {}).get("session_id", "") or "")

            def _m(r: FlowRun):
                c = dict(r.config or {})
                c["roberts_session_id"] = sid
                r.config = c
                _sync_run_from_roberts(project_id, r)

            run = _patch_run(project_id, str(run.get("run_id", "")), _m)
            store.append_ledger(
                project_id,
                {
                    "kind": "flow.hook.roberts.started",
                    "run_id": str(run.get("run_id", "")),
                    "session_id": sid,
                    "actor_id": str(started_by or "human.overseer"),
                },
            )
        except Exception as e:
            # Keep failed run visible for audit.
            finish_flow_run(
                project_id,
                run_id=str(run.get("run_id", "")),
                status="aborted",
                actor_id=str(started_by or "human.overseer"),
                note=f"roberts_start_failed: {e}",
            )
            raise ValueError(f"failed to start roberts session: {e}") from e
    return run


def list_flow_runs(project_id: str, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    rows = [FlowRun.from_dict(x) for x in store.load_runs(project_id)]
    rows = [_sync_run_from_roberts(project_id, x) for x in rows]
    if not include_inactive:
        rows = [x for x in rows if x.status in _ACTIVE_STATES]
    rows.sort(key=lambda x: float(x.updated_at or 0.0), reverse=True)
    return [x.to_dict() for x in rows]


def get_flow_run(project_id: str, run_id: str) -> dict[str, Any] | None:
    rows = [FlowRun.from_dict(x) for x in store.load_runs(project_id)]
    row = _find_run(rows, run_id)
    if not row:
        return None
    row = _sync_run_from_roberts(project_id, row)
    return row.to_dict()


def advance_flow_stage(
    project_id: str,
    *,
    run_id: str,
    next_stage: str,
    actor_id: str = "human.overseer",
    note: str = "",
) -> dict[str, Any]:
    ns = str(next_stage or "").strip()
    if not ns:
        raise ValueError("next_stage is required")

    def _mut(rows_raw: list[dict[str, Any]]):
        rows = [FlowRun.from_dict(x) for x in rows_raw]
        run = _find_run(rows, run_id)
        if not run:
            raise ValueError("run not found")
        if _is_roberts_flow(run):
            run = _sync_run_from_roberts(project_id, run)
            # For roberts-council, stage progression is driven by council actions.
            if ns != run.current_stage:
                raise ValueError(
                    f"roberts_council stage is engine-driven; current='{run.current_stage}', requested='{ns}'"
                )
            return [x.to_dict() for x in rows], run.to_dict()
        if run.status not in _ACTIVE_STATES:
            raise ValueError(f"run is not active: status={run.status}")
        if ns not in run.stages:
            raise ValueError(f"next_stage '{ns}' is not in flow stages")
        prev_stage = run.current_stage
        idx = run.stages.index(ns)
        if idx < int(run.stage_index):
            raise ValueError("cannot move backward by advance_flow_stage")
        run.stage_index = idx
        run.updated_at = float(time.time())
        if run.current_stage == run.stages[-1] and run.current_stage in {"completed", "done", "finish"}:
            run.status = "completed"
        store.append_ledger(
            project_id,
            {
                "kind": "flow.advance",
                "run_id": run.run_id,
                "from_stage": prev_stage,
                "to_stage": ns,
                "stage": run.current_stage,
                "actor_id": str(actor_id or "human.overseer"),
                "note": str(note or ""),
            },
        )
        return [x.to_dict() for x in rows], run.to_dict()

    return store.with_lock(project_id, _mut)


def finish_flow_run(
    project_id: str,
    *,
    run_id: str,
    status: str = "completed",
    actor_id: str = "human.overseer",
    note: str = "",
) -> dict[str, Any]:
    st = str(status or "completed").strip().lower()
    if st not in {"completed", "aborted", "paused", "active"}:
        raise ValueError("status must be completed|aborted|paused|active")

    def _mut(rows_raw: list[dict[str, Any]]):
        rows = [FlowRun.from_dict(x) for x in rows_raw]
        run = _find_run(rows, run_id)
        if not run:
            raise ValueError("run not found")
        if _is_roberts_flow(run):
            try:
                from gods.athena import council_engine

                if st == "paused":
                    council_engine.chair_action(project_id, action="pause", actor_id=str(actor_id or "human.overseer"))
                elif st == "active":
                    council_engine.chair_action(project_id, action="resume", actor_id=str(actor_id or "human.overseer"))
                elif st == "aborted":
                    council_engine.chair_action(project_id, action="terminate", actor_id=str(actor_id or "human.overseer"))
                elif st == "completed":
                    s0 = dict(council_engine.get_state(project_id) or {})
                    phase = str(s0.get("phase", "") or "")
                    if phase not in {"completed", "aborted"}:
                        raise ValueError("cannot force completed: roberts session not finished yet")
            except Exception as e:
                raise ValueError(f"roberts finish hook failed: {e}") from e
            run = _sync_run_from_roberts(project_id, run)
        run.status = st
        run.updated_at = float(time.time())
        if st == "completed":
            run.stage_index = len(run.stages) - 1 if run.stages else 0
        store.append_ledger(
            project_id,
            {
                "kind": "flow.finish",
                "run_id": run.run_id,
                "status": run.status,
                "stage": run.current_stage,
                "actor_id": str(actor_id or "human.overseer"),
                "note": str(note or ""),
            },
        )
        return [x.to_dict() for x in rows], run.to_dict()

    return store.with_lock(project_id, _mut)


def list_flow_ledger(project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    return store.list_ledger(project_id, limit=limit)
