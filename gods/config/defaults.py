"""Default config builders."""
from __future__ import annotations

from gods.config.models import ProjectConfig


def default_project_config() -> ProjectConfig:
    return ProjectConfig(name="Default World")


def default_projects() -> dict[str, ProjectConfig]:
    return {"default": default_project_config()}
