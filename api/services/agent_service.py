"""Agent use-case service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.agents import registry as agent_registry
from gods.config import AgentModelConfig, runtime_config
from gods.identity import HUMAN_AGENT_ID, is_valid_agent_id
from gods.iris import facade as iris_facade


class AgentService:
    @staticmethod
    def _derive_llm_state(row: dict[str, Any], queued: int) -> str:
        run_state = str(row.get("run_state", "") or "").strip().lower()
        event_type = str(row.get("current_event_type", "") or "").strip().lower()
        last_error = str(row.get("last_error", "") or "").lower()
        backoff_until = float(row.get("backoff_until", 0.0) or 0.0)

        if "429" in last_error or "rate limit" in last_error:
            return "throttled"
        if run_state == "error_backoff" or backoff_until > 0:
            return "backoff"
        if run_state == "running" and event_type:
            return "inflight"
        if queued > 0:
            return "queued"
        if run_state == "cooldown":
            return "cooldown"
        return "none"

    def status(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        active = agent_registry.list_active_agents(pid)
        rows = angelia_facade.list_agent_status(pid, active)
        items = []
        for row in rows:
            aid = row.get("agent_id", "")
            queued = int(row.get("queued_events", 0) or 0)
            worker_state = str(row.get("run_state", "idle") or "idle")
            llm_state = self._derive_llm_state(row, queued)
            items.append(
                {
                    "project_id": pid,
                    "agent_id": aid,
                    "worker_state": worker_state,
                    "llm_state": llm_state,
                    "last_reason": row.get("current_event_type", ""),
                    "last_pulse_at": float(row.get("last_wake_at", 0.0) or 0.0),
                    "next_eligible_at": max(
                        float(row.get("cooldown_until", 0.0) or 0.0),
                        float(row.get("backoff_until", 0.0) or 0.0),
                    ),
                    "empty_cycles": 0,
                    "last_next_step": "",
                    "last_error": row.get("last_error", ""),
                    "queued_pulse_events": queued,
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
        agent_registry.ensure_registry(project_id)
        agent_registry.register_agent(project_id, aid, active=False)
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
        agent_registry.unregister_agent(project_id, aid)
        proj = runtime_config.projects[project_id]
        if aid in proj.agent_settings:
            del proj.agent_settings[aid]
        runtime_config.save()
        return {"status": "success"}


agent_service = AgentService()
