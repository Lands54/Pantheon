"""Default config builders from declarative config blocks (SSOT)."""
from __future__ import annotations

import copy

from gods.config.blocks import PROJECT_DEFAULTS
from gods.config.models import ProjectConfig


def default_project_config() -> ProjectConfig:
    payload = copy.deepcopy(PROJECT_DEFAULTS)
    # Keep bootstrap project human-readable as before.
    payload["name"] = "Default World"
    return ProjectConfig(**payload)


def default_projects() -> dict[str, ProjectConfig]:
    return {"default": default_project_config()}
