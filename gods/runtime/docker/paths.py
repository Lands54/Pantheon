"""Path and naming helpers for docker runtime."""
from __future__ import annotations

import re
from pathlib import Path

from gods.paths import agent_dir as _agent_dir
from gods.paths import project_dir as _project_dir
from gods.paths import repo_root as _repo_root


def repo_root() -> Path:
    return _repo_root()


def project_root(project_id: str) -> Path:
    return _project_dir(project_id)


def agent_territory(project_id: str, agent_id: str) -> Path:
    return _agent_dir(project_id, agent_id)


def _slug(raw: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]", "-", str(raw))
    text = re.sub(r"-+", "-", text).strip("-")
    return text.lower() or "x"


def container_name(project_id: str, agent_id: str) -> str:
    return f"gods-{_slug(project_id)}-{_slug(agent_id)}"


def project_container_prefix(project_id: str) -> str:
    return f"gods-{_slug(project_id)}-"
