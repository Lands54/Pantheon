"""Assemble pulse frames for Janus from PulseLedger."""
from __future__ import annotations

import logging
from typing import Any

from gods.janus.pulse_contract import (
    PulseAgentResponseSegment,
    PulseFrame,
    PulseToolCallItem,
    PulseTriggerItem,
)
from gods.mnemosyne.facade import (
    PulseIntegrityReport,
    discard_incomplete_frames,
    group_pulses,
    list_pulse_entries,
    trim_truncated_head,
    validate_pulse_integrity,
)

logger = logging.getLogger(__name__)


def load_pulse_frames(
    project_id: str,
    agent_id: str,
    *,
    from_seq: int = 0,
    to_seq: int = 0,
    limit: int = 4000,
    allow_open_pulse_id: str = "",
) -> tuple[list[PulseFrame], list[str]]:
    """Load, validate, and convert raw ledger entries into PulseFrame objects.

    Returns (frames, critical_errors).  Only truly critical errors are
    returned; truncation artifacts and open-pulse warnings are handled
    gracefully and logged.
    """
    entries = list_pulse_entries(
        project_id,
        agent_id,
        from_seq=max(0, int(from_seq or 0)),
        to_seq=max(0, int(to_seq or 0)),
        limit=max(1, int(limit or 4000)),
    )
    raw_frames = group_pulses(entries)

    # Step 1: Discard ALL frames missing pulse.start (truncation artifacts
    # or write failures), not just the head.  The open pulse is exempt.
    open_pid = str(allow_open_pulse_id or "").strip()
    raw_frames = discard_incomplete_frames(raw_frames, allow_open_pulse_id=open_pid)

    # Step 2: Structured integrity validation.
    report = validate_pulse_integrity(raw_frames, allow_open_pulse_id=open_pid)

    # Log warnings for operator awareness (non-blocking).
    for w in report.warnings:
        logger.debug("PULSE_INTEGRITY_WARN: %s (project=%s, agent=%s)", w, project_id, agent_id)

    # Step 3: Convert raw frames to PulseFrame objects, skipping broken ones.
    frames: list[PulseFrame] = []
    for raw in raw_frames:
        # Skip frames with no trigger.event/mail at all (completely broken).
        if not raw.has_triggers:
            logger.warning(
                "PULSE_SKIP_NO_TRIGGER: pulse=%s has no trigger.event/mail, skipping",
                raw.pulse_id,
            )
            continue

        ts = 0.0
        if raw.start is not None:
            ts = float(raw.start.get("ts", 0.0) or 0.0)
        elif raw.triggers:
            ts = float(raw.triggers[0].get("ts", 0.0) or 0.0)
        frame = PulseFrame(pulse_id=raw.pulse_id, timestamp=ts)
        frame.state = "done" if raw.finish is not None else "processing"

        # Build trigger items from real trigger entries only.
        # pulse.start is lifecycle marker and not a trigger cause.
        for tr in raw.triggers:
            pld = dict(tr.get("payload", {}) or {})
            kind = str(tr.get("kind", "") or "")
            if kind == "trigger.mail":
                frame.triggers.append(
                    PulseTriggerItem(
                        kind="email",
                        origin=str(tr.get("origin", "internal") or "internal"),  # type: ignore[arg-type]
                        item_type=str(pld.get("msg_type", "mail") or "mail"),
                        item_id=str(pld.get("message_id", "") or pld.get("event_id", "")),
                        title=str(pld.get("title", "") or ""),
                        sender=str(pld.get("sender", "") or ""),
                        content=str(pld.get("content", "") or ""),
                    )
                )
            else:
                frame.triggers.append(
                    PulseTriggerItem(
                        kind="event",
                        origin=str(tr.get("origin", "internal") or "internal"),  # type: ignore[arg-type]
                        item_type=str(pld.get("event_type", "") or "event"),
                        item_id=str(pld.get("event_id", "") or ""),
                        content=str(pld.get("reason", "") or ""),
                    )
                )

        # Build interleaved agent-response segments from ledger seq order.
        by_call: dict[str, PulseToolCallItem] = {}
        call_first_seq: dict[str, int] = {}
        call_rendered: set[str] = set()
        stream = sorted(
            [*list(raw.llm or []), *list(raw.tools or [])],
            key=lambda x: (
                int(x.get("seq", 0) or 0),
                float(x.get("ts", 0.0) or 0.0),
                str(x.get("kind", "") or ""),
            ),
        )
        for row in stream:
            kind = str(row.get("kind", "") or "")
            pld = dict(row.get("payload", {}) or {})
            seq = int(row.get("seq", 0) or 0)
            if kind == "llm.response":
                txt = str(pld.get("content", "") or "").strip()
                if txt:
                    if frame.agent_response.text:
                        frame.agent_response.text += "\n" + txt
                    else:
                        frame.agent_response.text = txt
                    frame.agent_response.segments.append(
                        PulseAgentResponseSegment(kind="text", seq=seq, text=txt)
                    )
                continue

            call_id = str(pld.get("call_id", "") or "").strip()
            if not call_id:
                call_id = f"call_unknown_{len(by_call)+1}"
            if kind == "tool.call":
                item = by_call.get(call_id)
                if item is None:
                    item = PulseToolCallItem(
                        name=str(pld.get("tool_name", "") or "tool"),
                        call_id=call_id,
                        args=dict(pld.get("args", {}) or {}),
                    )
                    by_call[call_id] = item
                else:
                    item.args = dict(pld.get("args", {}) or item.args or {})
                call_first_seq.setdefault(call_id, seq)
            elif kind == "tool.result":
                item = by_call.get(call_id)
                if item is None:
                    item = PulseToolCallItem(name=str(pld.get("tool_name", "") or "tool"), call_id=call_id)
                    by_call[call_id] = item
                item.status = str(pld.get("status", "") or item.status)
                item.result = str(pld.get("result", "") or item.result)
                call_first_seq.setdefault(call_id, seq)
                frame.agent_response.segments.append(
                    PulseAgentResponseSegment(
                        kind="tool",
                        seq=seq,
                        tool_call=PulseToolCallItem(
                            name=item.name,
                            call_id=item.call_id,
                            status=item.status,
                            args=dict(item.args or {}),
                            result=item.result,
                        ),
                    )
                )
                call_rendered.add(call_id)
        # Render unresolved calls (no result yet) as placeholder tool segments once.
        for call_id, item in by_call.items():
            if call_id in call_rendered:
                continue
            frame.agent_response.segments.append(
                PulseAgentResponseSegment(
                    kind="tool",
                    seq=int(call_first_seq.get(call_id, 0) or 0),
                    tool_call=PulseToolCallItem(
                        name=item.name,
                        call_id=item.call_id,
                        status=item.status,
                        args=dict(item.args or {}),
                        result=item.result,
                    ),
                )
            )
        frame.agent_response.tool_calls = list(by_call.values())

        frames.append(frame)

    # Only return hard errors (not warnings) — callers decide policy.
    return frames, report.errors
