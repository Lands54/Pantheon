"""Janus structured journal + mnemosyne linkage helpers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.janus.models import ObservationRecord, TaskStateCard
from gods.paths import mnemosyne_dir


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _append_jsonl(path: Path, row: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-max(1, int(limit)) :]


def profile_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "agent_profiles" / f"{agent_id}.md"


def task_state_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "task_state" / f"{agent_id}.json"


def observations_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "observations" / f"{agent_id}.jsonl"


def inbox_digest_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "inbox_digest" / f"{agent_id}.jsonl"


def context_reports_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "context_reports" / f"{agent_id}.jsonl"


def read_profile(project_id: str, agent_id: str) -> str:
    prof = profile_path(project_id, agent_id)
    if not prof.exists():
        return ""
    try:
        return prof.read_text(encoding="utf-8")
    except Exception:
        return ""


def read_task_state(project_id: str, agent_id: str, objective_fallback: str = "") -> TaskStateCard:
    p = task_state_path(project_id, agent_id)
    if p.exists():
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
            return TaskStateCard(
                objective=str(row.get("objective", objective_fallback)),
                plan=list(row.get("plan", []) or []),
                progress=list(row.get("progress", []) or []),
                blockers=list(row.get("blockers", []) or []),
                next_actions=list(row.get("next_actions", []) or []),
            )
        except Exception:
            pass
    card = TaskStateCard(objective=objective_fallback)
    write_task_state(project_id, agent_id, card)
    return card


def write_task_state(project_id: str, agent_id: str, card: TaskStateCard):
    p = task_state_path(project_id, agent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "objective": card.objective,
        "plan": card.plan,
        "progress": card.progress,
        "blockers": card.blockers,
        "next_actions": card.next_actions,
        "updated_at": time.time(),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_observation(record: ObservationRecord):
    _append_jsonl(
        observations_path(record.project_id, record.agent_id),
        {
            "project_id": record.project_id,
            "agent_id": record.agent_id,
            "tool": record.tool_name,
            "args_summary": record.args_summary,
            "result_summary": record.result_summary,
            "status": record.status,
            "timestamp": record.timestamp,
        },
    )


def list_observations(project_id: str, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return _read_jsonl(observations_path(project_id, agent_id), limit=limit)


def record_inbox_digest(project_id: str, agent_id: str, event_ids: list[str], summary: str):
    _append_jsonl(
        inbox_digest_path(project_id, agent_id),
        {
            "project_id": project_id,
            "agent_id": agent_id,
            "event_ids": list(event_ids or []),
            "summary": summary,
            "timestamp": time.time(),
        },
    )


def write_context_report(project_id: str, agent_id: str, payload: dict[str, Any]):
    row = {
        "project_id": project_id,
        "agent_id": agent_id,
        "timestamp": time.time(),
        **(payload or {}),
    }
    _append_jsonl(context_reports_path(project_id, agent_id), row)


def list_context_reports(project_id: str, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl(context_reports_path(project_id, agent_id), limit=limit)


def latest_context_report(project_id: str, agent_id: str) -> dict[str, Any] | None:
    rows = list_context_reports(project_id, agent_id, limit=1)
    return rows[-1] if rows else None
