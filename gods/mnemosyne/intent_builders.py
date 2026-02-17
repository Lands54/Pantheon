"""Builders for converting runtime signals to typed MemoryIntent."""
from __future__ import annotations

import re
import time
from typing import Any

from gods.mnemosyne.contracts import MemoryIntent


def intent_from_angelia_event(event: Any, stage: str, extra_payload: dict[str, Any] | None = None) -> MemoryIntent:
    event_type = str(getattr(event, "event_type", "system") or "system")
    payload = {
        "stage": str(stage or "processing"),
        "event_id": str(getattr(event, "event_id", "")),
        "event_type": event_type,
        "priority": int(getattr(event, "priority", 0) or 0),
        "attempt": int(getattr(event, "attempt", 0) or 0),
        "max_attempts": int(getattr(event, "max_attempts", 0) or 0),
        "payload": getattr(event, "payload", {}) or {},
    }
    if extra_payload:
        payload.update(extra_payload)
    reason = str(payload.get("payload", {}).get("reason") or event_type)
    return MemoryIntent(
        intent_key=f"event.{event_type}",
        project_id=str(getattr(event, "project_id", "")),
        agent_id=str(getattr(event, "agent_id", "")),
        source_kind="event",
        payload=payload,
        fallback_text=f"[EVENT] type={event_type} stage={stage} reason={reason}",
        timestamp=time.time(),
    )


def intent_from_tool_result(
    project_id: str,
    agent_id: str,
    tool_name: str,
    status: str,
    args: dict[str, Any],
    result: str,
) -> MemoryIntent:
    st = str(status or "ok").strip().lower()
    if st not in {"ok", "blocked", "error"}:
        st = "error"
    tn = str(tool_name or "unknown").strip()
    raw_result = str(result or "")
    compact = _compact_tool_result(raw_result, max_len=900)
    return MemoryIntent(
        intent_key=f"tool.{tn}.{st}",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="tool",
        payload={
            "tool_name": tn,
            "status": st,
            "args": args or {},
            "result": raw_result[:2000],
            "result_compact": compact,
        },
        fallback_text=f"[[ACTION]] {tn} ({st}) -> {result}",
        timestamp=time.time(),
    )


def _compact_tool_result(text: str, max_len: int = 900) -> str:
    s = str(text or "")
    # redact noisy ids in plain text forms: key=value
    s = re.sub(r"\b(event_id|message_id|receipt_id|outbox_receipt_id|job_id)\s*=\s*[A-Za-z0-9_-]{8,}", r"\1=<redacted>", s)
    s = re.sub(r"\bid\s*=\s*[A-Za-z0-9_-]{8,}", "id=<redacted>", s)
    s = re.sub(r"\bmid\s*=\s*[A-Za-z0-9_-]{8,}", "mid=<redacted>", s)
    # redact noisy ids in JSON-like forms: "key": "value"
    s = re.sub(
        r'"(event_id|message_id|receipt_id|outbox_receipt_id|job_id)"\s*:\s*"[^"]{8,}"',
        r'"\1":"<redacted>"',
        s,
    )
    s = re.sub(r'"id"\s*:\s*"[^"]{8,}"', r'"id":"<redacted>"', s)
    return s[: max(80, int(max_len))]


def intent_from_llm_response(project_id: str, agent_id: str, phase: str, content: str) -> MemoryIntent:
    return MemoryIntent(
        intent_key="llm.response",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="llm",
        payload={"phase": str(phase or ""), "content": str(content or "")},
        fallback_text=str(content or "[No textual response]"),
        timestamp=time.time(),
    )


def intent_from_inbox_read(project_id: str, agent_id: str, delivered_ids: list[str], count: int) -> MemoryIntent:
    ids = [str(x) for x in list(delivered_ids or []) if str(x).strip()]
    return MemoryIntent(
        intent_key="inbox.read_ack",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload={"event_ids": ids, "count": int(count)},
        fallback_text=f"[INBOX_READ_ACK] count={int(count)} ids={','.join(ids)}",
        timestamp=time.time(),
    )


def intent_from_inbox_received(
    project_id: str,
    agent_id: str,
    title: str,
    sender: str,
    message_id: str,
    content: str = "",
    payload: dict[str, Any] | None = None,
    msg_type: str = "",
    intent_key: str = "inbox.received.unread",
) -> MemoryIntent:
    return MemoryIntent(
        intent_key=str(intent_key or "inbox.received.unread"),
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload={
            "title": title,
            "sender": sender,
            "message_id": message_id,
            "msg_type": str(msg_type or ""),
            "content": str(content or ""),
            "payload": payload or {},
        },
        fallback_text=f"[INBOX_UNREAD] title={title} from={sender} id={message_id}\n{str(content or '')[:200]}",
        timestamp=time.time(),
    )


def intent_from_inbox_summary(project_id: str, agent_id: str, summary_data: dict[str, Any]) -> MemoryIntent:
    payload = dict(summary_data or {})
    unread_count = int(payload.get("unread_count", 0) or 0)
    return MemoryIntent(
        intent_key="inbox.summary",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload=payload,
        fallback_text=f"[INBOX_SUMMARY] unread={unread_count}",
        timestamp=time.time(),
    )


def intent_from_outbox_status(
    project_id: str,
    agent_id: str,
    to_agent_id: str,
    title: str,
    message_id: str,
    status: str,
    error_message: str = "",
) -> MemoryIntent:
    st = str(status or "").strip().lower()
    if st not in {"pending", "delivered", "handled", "failed"}:
        st = "failed"
    payload = {
        "title": title,
        "to_agent_id": to_agent_id,
        "message_id": message_id,
        "status": st,
        "error_message": str(error_message or ""),
    }
    return MemoryIntent(
        intent_key=f"outbox.sent.{st}",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload=payload,
        fallback_text=f"[OUTBOX] title={title} to={to_agent_id} status={st} mid={message_id}",
        timestamp=time.time(),
    )


def intent_from_agent_marker(project_id: str, agent_id: str, marker: str, payload: dict[str, Any] | None = None) -> MemoryIntent:
    mk = str(marker or "").strip()
    mapping = {
        "freeform_mode": "agent.mode.freeform",
        "tool_loop_cap": "agent.safety.tool_loop_cap",
        "event_injected": "agent.event.injected",
    }
    key = mapping.get(mk, mk if "." in mk else f"agent.{mk}")
    data = dict(payload or {})
    if mk == "freeform_mode":
        fallback = "[MODE] freeform - phase state-machine bypassed."
    elif mk == "tool_loop_cap":
        fallback = "Reached tool loop safety cap in this pulse. Will continue next pulse."
    elif mk == "event_injected":
        fallback = f"[EVENT_INJECTED] {int(data.get('count', 0))} inbox event(s) appended after action."
    else:
        fallback = f"[AGENT_MARKER] {mk}"
    return MemoryIntent(
        intent_key=key,
        project_id=project_id,
        agent_id=agent_id,
        source_kind="agent",
        payload=data,
        fallback_text=fallback,
        timestamp=time.time(),
    )


def intent_from_phase_retry(project_id: str, agent_id: str, phase_name: str, message: str) -> MemoryIntent:
    phase = str(phase_name or "").strip().lower()
    if phase not in {"reason", "act", "observe"}:
        phase = "act"
    return MemoryIntent(
        intent_key=f"phase.retry.{phase}",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="phase",
        payload={"phase": phase, "message": str(message or "")},
        fallback_text=f"[PHASE_RETRY] {phase} -> {message}",
        timestamp=time.time(),
    )
