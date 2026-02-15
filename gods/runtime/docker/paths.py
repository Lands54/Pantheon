"""Path and naming helpers for docker runtime."""
from __future__ import annotations

import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def project_root(project_id: str) -> Path:
    return repo_root() / "projects" / project_id


def agent_territory(project_id: str, agent_id: str) -> Path:
    return project_root(project_id) / "agents" / agent_id


def _slug(raw: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]", "-", str(raw))
    text = re.sub(r"-+", "-", text).strip("-")
    return text.lower() or "x"


def container_name(project_id: str, agent_id: str) -> str:
    return f"gods-{_slug(project_id)}-{_slug(agent_id)}"


def project_container_prefix(project_id: str) -> str:
    return f"gods-{_slug(project_id)}-"
