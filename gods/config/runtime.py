"""Runtime config singleton and typed helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gods.config.loader import load_system_config
from gods.config.models import ProjectConfig, SystemConfig
from gods.identity import is_valid_agent_id
from gods.project import registry as project_registry


runtime_config = load_system_config()


def get_current_project() -> ProjectConfig:
    cur = project_registry.current_project()
    return runtime_config.projects.get(cur, ProjectConfig(name="Safety"))


def get_available_agents(project_id: str | None = None) -> list[str]:
    pid = project_id or project_registry.current_project()
    agents_dir = Path("projects") / pid / "agents"
    if not agents_dir.exists():
        return []
    out: list[str] = []
    for d in agents_dir.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not is_valid_agent_id(d.name):
            continue
        out.append(d.name)
    return out


def snapshot_runtime_config_payload() -> dict[str, Any]:
    cur = project_registry.current_project()
    proj = runtime_config.projects.get(cur)
    if not proj:
        runtime_config.projects["default"] = ProjectConfig(name="Default World")
    return {
        "openrouter_api_key": runtime_config.openrouter_api_key,
        "projects": runtime_config.projects,
    }


def apply_runtime_config_payload(data: dict[str, Any]) -> None:
    # Build a candidate config first to keep runtime_config immutable on save failure.
    candidate = SystemConfig(**runtime_config.model_dump())
    if "openrouter_api_key" in data:
        incoming = str(data["openrouter_api_key"] or "")
        if "*" not in incoming:
            candidate.openrouter_api_key = incoming
    if "projects" in data:
        for pid, pdata in data["projects"].items():
            k = str(pid)
            candidate.projects[k] = ProjectConfig(**dict(pdata or {}))

    # Persist candidate (strict normalize happens in save path).
    candidate.save()

    # Commit in-memory singleton only after successful save.
    runtime_config.openrouter_api_key = candidate.openrouter_api_key
    # current_project is runtime-managed by project registry
    runtime_config.projects = candidate.projects
