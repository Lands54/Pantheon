"""Chronos orchestrator: state window lifecycle for agent runtime."""
from __future__ import annotations

from typing import Any


class ChronosOrchestrator:
    @staticmethod
    def merge(project_id: str, agent_id: str, state: dict[str, Any]) -> None:
        # state_window was removed under zero-compat architecture.
        _ = (project_id, agent_id)
        if isinstance(state, dict):
            state.setdefault("messages", [])
        return

    @staticmethod
    def persist(project_id: str, agent_id: str, state: dict[str, Any]) -> None:
        _ = (project_id, agent_id, state)
        return

    @classmethod
    def finalize(cls, project_id: str, agent_id: str, state: dict[str, Any]) -> dict[str, Any]:
        cls.persist(project_id, agent_id, state)
        return state
