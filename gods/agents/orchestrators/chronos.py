"""Chronos orchestrator: state window lifecycle for agent runtime."""
from __future__ import annotations

from typing import Any

from gods.mnemosyne.facade import load_state_window, save_state_window


class ChronosOrchestrator:
    @staticmethod
    def merge(project_id: str, agent_id: str, state: dict[str, Any]) -> None:
        try:
            if not isinstance(state, dict):
                return
            if bool(state.get("__state_window_loaded", False)):
                return
            loaded = load_state_window(project_id, agent_id)
            current = list(state.get("messages", []) or [])
            if loaded:
                state["messages"] = loaded + current
            else:
                state.setdefault("messages", current)
            state["__state_window_loaded"] = True
        except Exception:
            return

    @staticmethod
    def persist(project_id: str, agent_id: str, state: dict[str, Any]) -> None:
        try:
            if not isinstance(state, dict):
                return
            msgs = list(state.get("messages", []) or [])
            if not msgs:
                return
            save_state_window(project_id, agent_id, msgs)
        except Exception:
            return

    @classmethod
    def finalize(cls, project_id: str, agent_id: str, state: dict[str, Any]) -> dict[str, Any]:
        cls.persist(project_id, agent_id, state)
        return state
