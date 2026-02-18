"""Mnemosyne-owned context material readers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.paths import mnemosyne_dir


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    if p.exists() and not p.is_dir():
        try:
            p.unlink()
        except Exception:
            pass
    p.mkdir(parents=True, exist_ok=True)
    return p


def profile_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "agent_profiles" / f"{agent_id}.md"


def task_state_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "task_state" / f"{agent_id}.json"


def observations_path(project_id: str, agent_id: str) -> Path:
    return _mn_root(project_id) / "observations" / f"{agent_id}.jsonl"


def chronicle_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "chronicles" / f"{agent_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


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


def read_profile(project_id: str, agent_id: str) -> str:
    prof = profile_path(project_id, agent_id)
    if not prof.exists():
        return ""
    try:
        return prof.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_agent_directives(project_id: str, agent_id: str) -> str:
    text = str(read_profile(project_id, agent_id) or "").strip()
    if text:
        return text
    return (
        f"Agent ID: {agent_id}\n"
        "No Mnemosyne profile found. Write directives to "
        f"projects/{project_id}/mnemosyne/agent_profiles/{agent_id}.md"
    )


def ensure_agent_memory_seeded(project_id: str, agent_id: str, directives: str, agent_workspace: Path):
    mem_path = chronicle_path(project_id, agent_id)
    if mem_path.exists():
        try:
            if mem_path.stat().st_size > 0:
                return
        except Exception:
            return
    agent_workspace.mkdir(parents=True, exist_ok=True)
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    seed = (
        "### SYSTEM_SEED\n"
        "Directives snapshot (from Mnemosyne profile):\n\n"
        f"{directives}\n\n---\n"
    )
    mem_path.write_text(seed, encoding="utf-8")


def read_task_state(project_id: str, agent_id: str, objective_fallback: str = "") -> dict[str, Any]:
    p = task_state_path(project_id, agent_id)
    if p.exists():
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(row, dict):
                return {
                    "objective": str(row.get("objective", objective_fallback)),
                    "plan": list(row.get("plan", []) or []),
                    "progress": list(row.get("progress", []) or []),
                    "blockers": list(row.get("blockers", []) or []),
                    "next_actions": list(row.get("next_actions", []) or []),
                }
        except Exception:
            pass
    payload = {
        "objective": str(objective_fallback or ""),
        "plan": [],
        "progress": [],
        "blockers": [],
        "next_actions": [],
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({**payload, "updated_at": time.time()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def list_observations(project_id: str, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return _read_jsonl(observations_path(project_id, agent_id), limit=limit)
