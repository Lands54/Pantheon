"""Interaction facade: submit interaction control events."""
from __future__ import annotations

from typing import Any

from gods import events as events_bus
from gods.interaction.contracts import (
    EVENT_DETACH_NOTICE,
    EVENT_HERMES_NOTICE,
    EVENT_MESSAGE_READ,
    EVENT_MESSAGE_SENT,
)
from gods.interaction.handler import register_handlers

def _dispatch_inline(record: events_bus.EventRecord) -> tuple[bool, dict[str, Any]]:
    register_handlers()
    handler = events_bus.get_handler(record.event_type)
    if handler is None:
        events_bus.transition_state(
            record.project_id,
            record.event_id,
            events_bus.EventState.DEAD,
            error_code="INTERACTION_HANDLER_MISSING",
            error_message=f"handler missing: {record.event_type}",
        )
        return False, {"error": "handler missing", "state": events_bus.EventState.DEAD.value}
    try:
        events_bus.transition_state(record.project_id, record.event_id, events_bus.EventState.PROCESSING)
        handler.on_pick(record)
        result = handler.on_process(record)
        handler.on_success(record, result if isinstance(result, dict) else {})
        events_bus.transition_state(record.project_id, record.event_id, events_bus.EventState.DONE)
        return True, (result if isinstance(result, dict) else {})
    except Exception as e:
        handler.on_fail(record, e)
        events_bus.transition_state(
            record.project_id,
            record.event_id,
            events_bus.EventState.DEAD,
            error_code="INTERACTION_HANDLER_ERROR",
            error_message=str(e),
        )
        handler.on_dead(record, e)
        return False, {"error": str(e), "state": events_bus.EventState.DEAD.value}


def submit_message_event(
    *,
    project_id: str,
    to_id: str,
    sender_id: str,
    title: str,
    content: str,
    msg_type: str,
    trigger_pulse: bool,
    priority: int,
    dedupe_key: str = "",
    event_type: str = EVENT_MESSAGE_SENT,
    meta: dict[str, Any] | None = None,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    attachment_ids = [str(x).strip() for x in list(attachments or []) if str(x).strip()]
    payload = {
        "agent_id": str(to_id or "").strip(),
        "to_id": str(to_id or "").strip(),
        "sender_id": str(sender_id or "").strip(),
        "title": str(title or "").strip(),
        "content": str(content or ""),
        "msg_type": str(msg_type or "private"),
        "trigger_pulse": bool(trigger_pulse),
        "mail_priority": int(priority),
        "attachments": attachment_ids,
    }
    rec = events_bus.EventRecord.create(
        project_id=project_id,
        domain="interaction",
        event_type=event_type,
        priority=int(priority),
        payload=payload,
        dedupe_key=str(dedupe_key or ""),
        max_attempts=3,
        meta=meta or {},
    )
    rec = events_bus.append_event(rec)
    ok, result = _dispatch_inline(rec)
    return {
        "event_id": rec.event_id,
        "event_type": rec.event_type,
        "state": ("done" if ok else rec.state.value),
        "project_id": project_id,
        "agent_id": payload["agent_id"],
        "meta": {**payload, **result},
    }


def submit_read_event(
    *,
    project_id: str,
    agent_id: str,
    event_ids: list[str],
    priority: int = 90,
    dedupe_key: str = "",
) -> dict[str, Any]:
    payload = {
        "agent_id": str(agent_id or "").strip(),
        "event_ids": [str(x) for x in (event_ids or []) if str(x).strip()],
    }
    rec = events_bus.EventRecord.create(
        project_id=project_id,
        domain="interaction",
        event_type=EVENT_MESSAGE_READ,
        priority=int(priority),
        payload=payload,
        dedupe_key=str(dedupe_key or ""),
        max_attempts=3,
        meta={"source": "interaction_facade"},
    )
    rec = events_bus.append_event(rec)
    _dispatch_inline(rec)
    return {
        "event_id": rec.event_id,
        "event_type": rec.event_type,
        "state": "done",
        "project_id": project_id,
        "agent_id": payload["agent_id"],
        "meta": payload,
    }


def submit_hermes_notice(
    *,
    project_id: str,
    targets: list[str],
    sender_id: str,
    title: str,
    content: str,
    msg_type: str,
    trigger_pulse: bool,
    priority: int,
    dedupe_prefix: str = "hermes_notice",
) -> list[str]:
    sent: list[str] = []
    for aid in [str(x).strip() for x in (targets or []) if str(x).strip()]:
        try:
            submit_message_event(
                project_id=project_id,
                to_id=aid,
                sender_id=sender_id,
                title=title,
                content=content,
                msg_type=msg_type,
                trigger_pulse=trigger_pulse,
                priority=priority,
                dedupe_key=f"{dedupe_prefix}:{aid}:{title}",
                event_type=EVENT_HERMES_NOTICE,
                meta={"source": "hermes"},
            )
            sent.append(aid)
        except Exception:
            continue
    return sent


def submit_detach_notice(
    *,
    project_id: str,
    agent_id: str,
    title: str,
    content: str,
    msg_type: str = "detach_notice",
    trigger_pulse: bool = True,
    priority: int = 60,
    dedupe_key: str = "",
) -> dict[str, Any]:
    return submit_message_event(
        project_id=project_id,
        to_id=agent_id,
        sender_id="runtime.detach",
        title=title,
        content=content,
        msg_type=msg_type,
        trigger_pulse=trigger_pulse,
        priority=priority,
        dedupe_key=dedupe_key,
        event_type=EVENT_DETACH_NOTICE,
        meta={"source": "detach"},
    )
