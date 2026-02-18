"""Nike orchestrator: runtime execution bridge for agent process."""
from __future__ import annotations

from typing import Any

from gods.agents.runtime import run_agent_runtime


class NikeOrchestrator:
    @staticmethod
    def run(project: Any, state: dict[str, Any]) -> dict[str, Any]:
        out = run_agent_runtime(project, state)
        if isinstance(out, dict) and "finalize_control" in out:
            out["__finalize_control"] = out.get("finalize_control")
        return out
