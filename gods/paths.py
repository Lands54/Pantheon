"""Unified filesystem path helpers for runtime and workspace domains."""
from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def projects_root() -> Path:
    return repo_root() / "projects"


def project_dir(project_id: str) -> Path:
    return projects_root() / str(project_id)


def agent_dir(project_id: str, agent_id: str) -> Path:
    return project_dir(project_id) / "agents" / str(agent_id)


def runtime_dir(project_id: str) -> Path:
    return project_dir(project_id) / "runtime"


def runtime_locks_dir(project_id: str) -> Path:
    return runtime_dir(project_id) / "locks"


def runtime_debug_dir(project_id: str, agent_id: str) -> Path:
    return runtime_dir(project_id) / "debug" / str(agent_id)


def mnemosyne_dir(project_id: str) -> Path:
    return project_dir(project_id) / "mnemosyne"


def project_buffers_dir(project_id: str) -> Path:
    return project_dir(project_id) / "buffers"
