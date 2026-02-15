"""
Backward-compatible server module.
Prefer using `api.app` (composition root) and root-level `server.py` for launching.
"""
from __future__ import annotations

from api.app import app
from api.services import simulation_service


def pause_all_projects_on_startup() -> int:
    """Backward-compatible alias for tests/legacy imports."""
    return simulation_service.pause_all_projects_on_startup()
