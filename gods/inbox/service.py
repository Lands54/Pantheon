"""Inbox service orchestration for event-driven delivery."""
from __future__ import annotations

from gods.inbox.models import InboxEvent, InboxMessageState
from gods.inbox.store import (
    enqueue_inbox_event,
    has_pending_inbox_events,
    list_inbox_events,
    mark_inbox_events_handled,
    take_deliverable_inbox_events,
)
from gods.pulse.queue import enqueue_pulse_event


def enqueue_message(
    *,
    project_id: str,
    agent_id: str,
    sender: str,
    content: str,
    msg_type: str,
    trigger_pulse: bool,
    pulse_priority: int,
) -> dict:
    event = enqueue_inbox_event(
        project_id=project_id,
        agent_id=agent_id,
        sender=sender,
        content=content,
        msg_type=msg_type,
    )
    pulse_event = None
    if trigger_pulse:
        pulse_event = enqueue_pulse_event(
            project_id=project_id,
            agent_id=agent_id,
            event_type="inbox_event",
            priority=pulse_priority,
            payload={"inbox_event_id": event.event_id},
        )
    return {
        "inbox_event_id": event.event_id,
        "pulse_event_id": (pulse_event.event_id if pulse_event else ""),
    }


def fetch_inbox_context(project_id: str, agent_id: str, budget: int) -> tuple[str, list[str]]:
    events = take_deliverable_inbox_events(project_id, agent_id, budget)
    if not events:
        return "", []

    lines = []
    for item in events:
        lines.append(
            f"- [{item.msg_type}] from={item.sender} at={item.created_at:.3f} id={item.event_id}: {item.content}"
        )
    text = "[Event Inbox Delivery]\n" + "\n".join(lines)
    return text, [item.event_id for item in events]


def ack_handled(project_id: str, event_ids: list[str]):
    mark_inbox_events_handled(project_id, event_ids)


def has_pending(project_id: str, agent_id: str) -> bool:
    return has_pending_inbox_events(project_id, agent_id)


def list_events(
    project_id: str,
    agent_id: str | None,
    state: InboxMessageState | None,
    limit: int,
) -> list[InboxEvent]:
    return list_inbox_events(project_id, agent_id=agent_id, state=state, limit=limit)
