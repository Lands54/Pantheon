"""Unified agent runtime entry powered by LangGraph."""
from __future__ import annotations

import logging
import time
import uuid

from gods.agents.runtime.models import RuntimeState
from gods.config import runtime_config
from gods.metis.strategy_runtime import run_metis_strategy
from gods.mnemosyne.facade import append_pulse_entry

logger = logging.getLogger(__name__)


def _max_rounds(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
    return max(1, min(value, 64))


def run_agent_runtime(agent, state: RuntimeState):
    """Execute the agent runtime loop (LangGraph-powered).

    Pulse lifecycle notes:
    - If __pulse_meta is NOT set (direct/local invocation), this function
      creates a local pulse.start + trigger.event AND writes pulse.finish.
    - If __pulse_meta IS set (normal Angelia worker path), pulse.start was
      already written by worker, and pulse.finish is written by worker after
      this function returns.  Engine does NOT duplicate pulse.finish in
      that case.
    """
    state["agent_id"] = agent.agent_id
    state["project_id"] = agent.project_id
    state.setdefault("messages", [])
    state.setdefault("next_step", "")
    state["loop_count"] = int(state.get("loop_count", 0) or 0)
    state["max_rounds"] = _max_rounds(agent.project_id)

    pulse_meta = dict(state.get("__pulse_meta", {}) or {})
    is_local_pulse = False

    if not str(pulse_meta.get("pulse_id", "") or "").strip():
        # No pulse_id set — this is a direct/local invocation.
        # Engine owns the full pulse lifecycle in this case.
        is_local_pulse = True
        pulse_meta["pulse_id"] = f"pulse_local_{uuid.uuid4().hex[:12]}"
        pulse_meta["reason"] = str(pulse_meta.get("reason", "direct_process") or "direct_process")
        pulse_meta["started_at"] = float(time.time())
        state["__pulse_meta"] = pulse_meta
        try:
            append_pulse_entry(
                agent.project_id,
                agent.agent_id,
                pulse_id=str(pulse_meta["pulse_id"]),
                kind="pulse.start",
                payload={
                    "pulse_id": str(pulse_meta["pulse_id"]),
                    "reason": str(pulse_meta.get("reason", "direct_process")),
                    "trigger_count": 1,
                    "trigger_event_ids": [],
                    "trigger_event_types": ["direct_process"],
                    "base_intent_seq": int(state.get("__chaos_synced_seq", 0) or 0),
                },
                origin="internal",
            )
            append_pulse_entry(
                agent.project_id,
                agent.agent_id,
                pulse_id=str(pulse_meta["pulse_id"]),
                kind="trigger.event",
                payload={
                    "event_type": "direct_process",
                    "event_id": "",
                    "reason": str(pulse_meta.get("reason", "direct_process")),
                },
                origin="internal",
            )
        except Exception as exc:
            logger.warning("PULSE_START_WRITE_FAIL: %s", exc)

    state["pulse_meta"] = pulse_meta
    out = run_metis_strategy(agent, state)

    # Only write pulse.finish if this is a local pulse (engine owns lifecycle).
    # For Angelia worker path, worker.py writes the authoritative pulse.finish
    # with richer metadata (ACK, finalize_control, etc).
    if is_local_pulse:
        try:
            llm_text = _extract_last_llm_text(out)
            append_pulse_entry(
                agent.project_id,
                agent.agent_id,
                pulse_id=str(pulse_meta["pulse_id"]),
                kind="pulse.finish",
                payload={
                    "pulse_id": str(pulse_meta["pulse_id"]),
                    "next_step": str(out.get("next_step", "") or ""),
                    "finalize_mode": str(dict(out.get("finalize_control", {}) or {}).get("mode", "") or ""),
                    "tool_call_count": len(list(out.get("tool_calls", []) or [])) if isinstance(out, dict) else 0,
                    "tool_result_count": len(list(out.get("tool_results", []) or [])) if isinstance(out, dict) else 0,
                    "llm_text_len": len(llm_text),
                    "error": "",
                },
                origin="internal",
            )
        except Exception as exc:
            logger.warning("PULSE_FINISH_WRITE_FAIL: %s", exc)

    if "finalize_control" in out:
        out["__finalize_control"] = out.get("finalize_control")
    return out


def _extract_last_llm_text(state: dict) -> str:
    """Extract the last non-empty LLM text content from messages."""
    for msg in reversed(list(state.get("messages", []) or [])):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return ""
