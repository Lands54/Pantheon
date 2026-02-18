"""Interaction event handlers."""
from __future__ import annotations

from gods import events as events_bus
from gods.interaction.contracts import (
    EVENT_DETACH_NOTICE,
    EVENT_HERMES_NOTICE,
    EVENT_MESSAGE_READ,
    EVENT_MESSAGE_SENT,
)
from gods.interaction.errors import InteractionError
from gods.iris import facade as iris_facade
from gods.mnemosyne import facade as mnemosyne_facade


def _require_str(payload: dict, key: str) -> str:
    val = str(payload.get(key, "")).strip()
    if not val:
        raise InteractionError("INTERACTION_BAD_REQUEST", f"{key} is required")
    return val


class _MessageHandler(events_bus.EventHandler):
    def on_process(self, record: events_bus.EventRecord) -> dict:
        payload = record.payload or {}
        to_id = _require_str(payload, "to_id") if str(payload.get("to_id", "")).strip() else _require_str(payload, "agent_id")
        sender_id = _require_str(payload, "sender_id")
        title = _require_str(payload, "title")
        content = str(payload.get("content", ""))
        msg_type = str(payload.get("msg_type", "private")).strip() or "private"
        trigger_pulse = bool(payload.get("trigger_pulse", True))
        priority = int(payload.get("mail_priority", payload.get("priority", record.priority)))
        attachments = [str(x).strip() for x in list(payload.get("attachments", []) or []) if str(x).strip()]
        for aid in attachments:
            try:
                ref = mnemosyne_facade.head_artifact(aid, sender_id, record.project_id)
            except Exception as e:
                raise InteractionError("INTERACTION_BAD_REQUEST", f"attachment not accessible: {aid}: {e}") from e
            if str(ref.scope) != "agent":
                raise InteractionError("INTERACTION_BAD_REQUEST", f"attachment must be agent-scope: {aid}")
            try:
                mnemosyne_facade.grant_artifact_access(aid, record.project_id, sender_id, to_id)
            except Exception as e:
                raise InteractionError("INTERACTION_BAD_REQUEST", f"attachment grant failed: {aid}: {e}") from e
        out = iris_facade.enqueue_message(
            project_id=record.project_id,
            agent_id=to_id,
            sender=sender_id,
            title=title,
            content=content,
            msg_type=msg_type,
            trigger_pulse=trigger_pulse,
            pulse_priority=priority,
            attachments=attachments,
        )
        return {"ok": True, "mail_event_id": out.get("mail_event_id", ""), "to_id": to_id}


class _ReadHandler(events_bus.EventHandler):
    def on_process(self, record: events_bus.EventRecord) -> dict:
        payload = record.payload or {}
        agent_id = _require_str(payload, "agent_id")
        event_ids = [str(x) for x in (payload.get("event_ids", []) or []) if str(x).strip()]
        if not event_ids:
            raise InteractionError("INTERACTION_BAD_REQUEST", "event_ids is required")
        iris_facade.ack_handled(record.project_id, event_ids, agent_id)
        return {"ok": True, "count": len(event_ids), "agent_id": agent_id}


_MESSAGE_HANDLER = _MessageHandler()
_READ_HANDLER = _ReadHandler()


def register_handlers():
    events_bus.register_handler(EVENT_MESSAGE_SENT, _MESSAGE_HANDLER)
    events_bus.register_handler(EVENT_HERMES_NOTICE, _MESSAGE_HANDLER)
    events_bus.register_handler(EVENT_DETACH_NOTICE, _MESSAGE_HANDLER)
    events_bus.register_handler(EVENT_MESSAGE_READ, _READ_HANDLER)
