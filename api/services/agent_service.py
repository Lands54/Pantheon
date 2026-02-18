"""Agent use-case service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.config import AgentModelConfig, runtime_config
from gods.identity import HUMAN_AGENT_ID, is_valid_agent_id
from gods.iris import facade as iris_facade


class AgentService:
    def status(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        proj = runtime_config.projects.get(pid)
        active = list(proj.active_agents) if proj else []
        rows = angelia_facade.list_agent_status(pid, active)
        items = []
        for row in rows:
            aid = row.get("agent_id", "")
            items.append(
                {
                    "project_id": pid,
                    "agent_id": aid,
                    "status": row.get("run_state", "idle"),
                    "last_reason": row.get("current_event_type", ""),
                    "last_pulse_at": float(row.get("last_wake_at", 0.0) or 0.0),
                    "next_eligible_at": max(
                        float(row.get("cooldown_until", 0.0) or 0.0),
                        float(row.get("backoff_until", 0.0) or 0.0),
                    ),
                    "empty_cycles": 0,
                    "last_next_step": "",
                    "last_error": row.get("last_error", ""),
                    "queued_pulse_events": int(row.get("queued_events", 0)),
                    "has_pending_inbox": bool(iris_facade.has_pending(pid, aid)),
                }
            )
        return {"project_id": pid, "agents": items}

    def create(self, agent_id: str, directives: str) -> dict[str, str]:
        project_id = resolve_project(None)
        aid = str(agent_id or "").strip()
        if not aid:
            raise HTTPException(status_code=400, detail="agent_id is required")
        if aid == HUMAN_AGENT_ID:
            raise HTTPException(status_code=400, detail="agent_id is reserved for human identity")
        if not is_valid_agent_id(aid):
            raise HTTPException(
                status_code=400,
                detail="invalid agent_id; expected ^[a-z][a-z0-9_]{0,63}$",
            )
        agent_dir = Path("projects") / project_id / "agents" / aid
        if agent_dir.exists():
            raise HTTPException(status_code=400, detail="Agent exists")

        agent_dir.mkdir(parents=True)
        profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{aid}.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(str(directives or ""), encoding="utf-8")

        proj = runtime_config.projects[project_id]
        if aid not in proj.agent_settings:
            proj.agent_settings[aid] = AgentModelConfig()
        runtime_config.save()
        return {"status": "success"}

    def delete(self, agent_id: str) -> dict[str, str]:
        project_id = resolve_project(None)
        aid = str(agent_id or "").strip()
        if not aid:
            raise HTTPException(status_code=400, detail="agent_id is required")
        agent_dir = Path("projects") / project_id / "agents" / aid
        if not agent_dir.exists():
            raise HTTPException(status_code=404, detail="Agent not found")

        shutil.rmtree(agent_dir)
        profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{aid}.md"
        if profile.exists():
            profile.unlink()
        proj = runtime_config.projects[project_id]
        if aid in proj.active_agents:
            proj.active_agents.remove(aid)
        if aid in proj.agent_settings:
            del proj.agent_settings[aid]
        runtime_config.save()
        return {"status": "success"}


agent_service = AgentService()
