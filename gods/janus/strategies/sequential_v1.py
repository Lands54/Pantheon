"""Janus sequential strategy (PulseLedger-only)."""
from __future__ import annotations

from gods.janus.models import ContextBuildRequest, ContextBuildResult
from gods.janus.pulse_assembler import load_pulse_frames
from gods.janus.pulse_formatter import render_tagged_context


class SequentialV1Strategy:
    """Build LLM context from PulseLedger frames only (no chronicle cards)."""

    def build(self, req: ContextBuildRequest) -> ContextBuildResult:
        mats = req.context_materials
        profile = str(getattr(mats, "profile", "") or "")
        directives = str(req.directives or getattr(mats, "directives", "") or "")
        task_state = str(getattr(mats, "task_state", "") or "")
        tools = str(req.tools_desc or getattr(mats, "tools", "") or "")
        inbox_hint = str(req.inbox_hint or getattr(mats, "inbox_hint", "") or "")

        pulse_limit = int(req.context_cfg.get("pulse_limit", 200) or 200)
        pulse_limit = max(1, min(pulse_limit, 2000))
        # Important: fetch a much wider window first, otherwise high-frequency heartbeat
        # pulses can evict meaningful llm/tool pulses before filtering.
        pulse_scan_limit = int(req.context_cfg.get("pulse_scan_limit", 0) or 0)
        if pulse_scan_limit <= 0:
            pulse_scan_limit = max(1000, pulse_limit * 12)
        pulse_scan_limit = max(pulse_limit, min(pulse_scan_limit, 20000))

        # Resolve current open pulse_id to exempt from missing-finish checks.
        open_pid = str(((req.state or {}).get("__pulse_meta", {}) or {}).get("pulse_id", "") or "")
        if not open_pid:
            open_pid = str(((req.state or {}).get("pulse_meta", {}) or {}).get("pulse_id", "") or "")

        frames, integrity_errors = load_pulse_frames(
            req.project_id,
            req.agent_id,
            limit=pulse_scan_limit,
            allow_open_pulse_id=open_pid,
        )

        if integrity_errors:
            raise ValueError(
                "PULSE_INTEGRITY_ERROR: "
                + "; ".join([str(x) for x in integrity_errors[:8]])
            )

        raw_count = len(frames)
        # Enforce trigger semantics: pulse.start is lifecycle marker, never a trigger.
        for fr in frames:
            fr.triggers = [
                tr for tr in list(fr.triggers or [])
                if str(getattr(tr, "item_type", "") or "").strip().lower() != "pulse.start"
            ]
        if len(frames) > pulse_limit:
            frames = frames[-pulse_limit:]

        for fr in frames:
            if not fr.triggers:
                raise ValueError(f"PULSE_EMPTY_TRIGGER: pulse_id={fr.pulse_id}")

        tagged_context = render_tagged_context(
            profile_text=profile,
            directives_text=directives,
            task_state_text=task_state,
            tools_text=tools,
            inbox_hint_text=inbox_hint,
            pulse_frames=frames,
        )

        return ContextBuildResult(
            strategy_used="sequential_v1",
            system_blocks=[tagged_context],
            token_usage={"total": 0, "chronicle": 0},
            preview={
                "pulse_count": len(frames),
                "pulse_raw_count": raw_count,
                "integrity_error_count": len(integrity_errors),
                "mode": "pulse_ledger_only",
            },
        )
