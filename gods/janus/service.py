"""Janus service entrypoint for context building."""
from __future__ import annotations

import json
import time
from typing import Any

from gods.agents.context_policy import resolve_context_cfg
from gods.janus.assembler import assemble_llm_messages
from gods.janus.journal import latest_context_report, list_context_reports, write_context_report
from gods.janus.models import ContextBuildRequest
from gods.janus.registry import get_strategy


class JanusService:
    def build_llm_messages(self, req: ContextBuildRequest) -> tuple[list[Any], dict[str, Any]]:
        cfg = resolve_context_cfg(req.project_id, req.agent_id)
        req.context_cfg = cfg
        strategy = get_strategy(cfg.get("strategy", "structured_v1"))
        result = strategy.build(req)
        messages = assemble_llm_messages(result)
        report = {
            "strategy_used": result.strategy_used,
            "token_usage": result.token_usage,
            "preview": result.preview,
            "phase": req.phase_name,
            "agent_id": req.agent_id,
        }
        if bool(cfg.get("write_build_report", True)):
            write_context_report(req.project_id, req.agent_id, report)
        return messages, report

    def context_preview(self, project_id: str, agent_id: str) -> dict[str, Any] | None:
        return latest_context_report(project_id, agent_id)

    def context_reports(self, project_id: str, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return list_context_reports(project_id, agent_id, limit=limit)


janus_service = JanusService()
