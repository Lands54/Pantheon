"""Bootstrap/migration helpers for runtime registries."""
from __future__ import annotations

from typing import Any

from gods.agents import registry as agent_registry
from gods.project import registry as project_registry


def migrate_runtime_registries_from_config(config_projects: dict[str, Any], current_project: str = "default") -> dict[str, Any]:
    pids = [str(x).strip() for x in list((config_projects or {}).keys()) if str(x).strip()]
    if "default" not in pids:
        pids.insert(0, "default")
    state = project_registry.ensure_registry(pids, current_project=current_project or "default")
    for pid in pids:
        proj = (config_projects or {}).get(pid)
        legacy_active = []
        if proj is not None:
            try:
                legacy_active = list(getattr(proj, "active_agents", []) or [])
            except Exception:
                legacy_active = []
        agent_registry.ensure_registry(pid, legacy_active_agents=legacy_active)
    return {
        "projects": list(state.get("projects", []) or []),
        "current_project": str(state.get("current_project", "default") or "default"),
    }

