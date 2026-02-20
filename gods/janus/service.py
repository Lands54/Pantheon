"""Janus service entrypoint for context building."""
from __future__ import annotations

from typing import Any

from gods.janus.assembler import assemble_llm_messages
from gods.janus.context_policy import resolve_context_cfg
from gods.janus.models import ContextBuildRequest
from gods.janus.registry import get_strategy
from gods.mnemosyne.facade import record_context_report


class JanusService:
    def build_llm_messages_from_envelope(
        self,
        agent: Any,
        *,
        envelope: Any,
        directives: str,
        local_memory: str,
        inbox_hint: str,
        tools_desc: str,
        phase_block: str = "",
    ) -> tuple[list[Any], dict[str, Any]]:
        state = dict(getattr(envelope, "state", {}) or {})
        snapshot = getattr(envelope, "resource_snapshot", None)
        context_materials = getattr(snapshot, "context_materials", None)
        if context_materials is None:
            from gods.chaos.contracts import MemoryMaterials
            context_materials = MemoryMaterials()
        state["__context_materials"] = context_materials
        strategy = str(getattr(envelope, "strategy", state.get("strategy", "react_graph")) or "react_graph")
        req = ContextBuildRequest(
            project_id=str(state.get("project_id", "")),
            agent_id=str(state.get("agent_id", "")),
            agent=agent,
            state=state,
            directives=directives,
            local_memory=local_memory,
            inbox_hint=inbox_hint,
            phase_name=strategy,
            phase_block=phase_block,
            tools_desc=tools_desc,
            context_materials=context_materials,
        )
        return self._build_llm_messages(req)

    def _build_llm_messages(self, req: ContextBuildRequest) -> tuple[list[Any], dict[str, Any]]:
        cfg = resolve_context_cfg(req.project_id, req.agent_id)
        req.context_cfg = cfg
        strategy = get_strategy(cfg.get("strategy", "sequential_v1"))
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
            record_context_report(req.project_id, req.agent_id, report)
        return messages, report

janus_service = JanusService()
