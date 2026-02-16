"""Inbox service orchestration for event-driven delivery."""
from __future__ import annotations

from typing import Any, Callable

from gods.inbox.models import InboxEvent, InboxMessageState
from gods.inbox.outbox_models import OutboxReceipt, OutboxReceiptStatus
from gods.inbox.outbox_store import create_receipt, list_receipts, update_status_by_message_id
from gods.inbox.store import (
    enqueue_inbox_event,
    has_pending_inbox_events,
    list_inbox_events,
    mark_inbox_events_handled,
    take_deliverable_inbox_events,
)
from gods.mnemosyne import record_intent
from gods.mnemosyne.intent_builders import (
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_outbox_status,
)

_WAKE_ENQUEUE: Callable[..., dict[str, Any]] | None = None


def set_wake_enqueue(func: Callable[..., dict[str, Any]] | None):
    """Register wake event enqueuer without creating hard module dependency."""
    global _WAKE_ENQUEUE
    _WAKE_ENQUEUE = func


def enqueue_message(
    *,
    project_id: str,
    agent_id: str,
    sender: str,
    title: str,
    content: str,
    msg_type: str,
    trigger_pulse: bool,
    pulse_priority: int,
) -> dict:
    if not str(title or "").strip():
        raise ValueError("title is required")
    event = enqueue_inbox_event(
        project_id=project_id,
        agent_id=agent_id,
        sender=sender,
        title=title,
        content=content,
        msg_type=msg_type,
    )
    receipt = create_receipt(
        project_id=project_id,
        from_agent_id=sender,
        to_agent_id=agent_id,
        title=title,
        message_id=event.event_id,
        status=OutboxReceiptStatus.PENDING,
    )
    record_intent(
        intent_from_inbox_received(
            project_id=project_id,
            agent_id=agent_id,
            title=title,
            sender=sender,
            message_id=event.event_id,
        )
    )
    record_intent(
        intent_from_outbox_status(
            project_id=project_id,
            agent_id=sender,
            to_agent_id=agent_id,
            title=title,
            message_id=event.event_id,
            status=receipt.status.value,
        )
    )
    pulse_event = None
    if trigger_pulse and _WAKE_ENQUEUE is not None:
        try:
            pulse_event = _WAKE_ENQUEUE(
                project_id=project_id,
                agent_id=agent_id,
                event_type="inbox_event",
                priority=pulse_priority,
                payload={"inbox_event_id": event.event_id},
            )
        except Exception as e:
            failed_rows = update_status_by_message_id(
                project_id=project_id,
                message_id=event.event_id,
                status=OutboxReceiptStatus.FAILED,
                error_message=str(e),
            )
            for item in failed_rows:
                record_intent(
                    intent_from_outbox_status(
                        project_id=project_id,
                        agent_id=item.from_agent_id,
                        to_agent_id=item.to_agent_id,
                        title=item.title,
                        message_id=item.message_id,
                        status=item.status.value,
                        error_message=item.error_message,
                    )
                )
            raise
    return {
        "inbox_event_id": event.event_id,
        "title": title,
        "outbox_receipt_id": receipt.receipt_id,
        "outbox_status": receipt.status.value,
        "pulse_event_id": (pulse_event.get("event_id", "") if pulse_event else ""),
    }


def fetch_inbox_context(project_id: str, agent_id: str, budget: int) -> tuple[str, list[str]]:
    events = take_deliverable_inbox_events(project_id, agent_id, budget)
    if not events:
        return "", []
    for item in events:
        updated = update_status_by_message_id(
            project_id=project_id,
            message_id=item.event_id,
            status=OutboxReceiptStatus.DELIVERED,
        )
        for rec in updated:
            record_intent(
                intent_from_outbox_status(
                    project_id=project_id,
                    agent_id=rec.from_agent_id,
                    to_agent_id=rec.to_agent_id,
                    title=rec.title,
                    message_id=rec.message_id,
                    status=rec.status.value,
                )
            )

    lines = []
    for item in events:
        lines.append(
            f"- [title={item.title}][from={item.sender}][status={item.state.value}] at={item.created_at:.3f} id={item.event_id}: {item.content}"
        )
    ids = [item.event_id for item in events]
    read_recent = list_inbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=InboxMessageState.HANDLED,
        limit=max(1, min(budget, 10)),
    )
    receipts = list_receipts(project_id=project_id, from_agent_id=agent_id, limit=max(1, min(budget * 3, 50)))
    unread_count = len(
        list_inbox_events(project_id=project_id, agent_id=agent_id, state=InboxMessageState.PENDING, limit=1000)
    ) + len(
        list_inbox_events(project_id=project_id, agent_id=agent_id, state=InboxMessageState.DEFERRED, limit=1000)
    )
    status_count = {"pending": 0, "delivered": 0, "handled": 0, "failed": 0}
    for r in receipts:
        if r.status.value in status_count:
            status_count[r.status.value] += 1

    text = (
        "[INBOX SUMMARY]\n"
        + f"- unread_count={unread_count}\n"
        + f"- read_recent_count={len(read_recent)}\n"
        + f"- sent_pending={status_count['pending']} sent_delivered={status_count['delivered']} "
        + f"sent_handled={status_count['handled']} sent_failed={status_count['failed']}\n"
        + "\n[INBOX UNREAD]\n"
        + ("\n".join(lines) if lines else "- (none)")
        + "\n\n[INBOX READ RECENT]\n"
        + (
            "\n".join(
                [
                    f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f}"
                    for x in read_recent[-10:]
                ]
            )
            if read_recent
            else "- (none)"
        )
        + "\n\n[SENT RECEIPTS]\n"
        + (
            "\n".join(
                [
                    f"- [title={r.title}][to={r.to_agent_id}][status={r.status.value}] mid={r.message_id} updated={r.updated_at:.3f}"
                    for r in receipts[:20]
                ]
            )
            if receipts
            else "- (none)"
        )
        + "\n\n[Inbox Status Note]\n"
        + f"- Delivered this pulse: {', '.join(ids)}\n"
        + "- These delivered messages will be marked handled automatically after this pulse.\n"
        + "- Avoid repeated confirmation polling; proceed with execution."
    )
    try:
        from gods.janus import record_inbox_digest

        record_inbox_digest(
            project_id=project_id,
            agent_id=agent_id,
            event_ids=ids,
            summary=f"Delivered {len(ids)} inbox message(s) this pulse.",
        )
    except Exception:
        pass
    return text, ids


def build_inbox_overview(project_id: str, agent_id: str, budget: int = 20) -> str:
    budget = max(1, int(budget))
    unread = list_inbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=InboxMessageState.PENDING,
        limit=budget,
    ) + list_inbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=InboxMessageState.DEFERRED,
        limit=budget,
    )
    unread.sort(key=lambda x: x.created_at)
    unread = unread[-budget:]
    read_recent = list_inbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=InboxMessageState.HANDLED,
        limit=max(1, budget // 2),
    )
    receipts = list_receipts(project_id=project_id, from_agent_id=agent_id, limit=max(1, budget * 2))

    status_count = {"pending": 0, "delivered": 0, "handled": 0, "failed": 0}
    for r in receipts:
        if r.status.value in status_count:
            status_count[r.status.value] += 1

    text = (
        "[INBOX SUMMARY]\n"
        + f"- unread_count={len(unread)}\n"
        + f"- read_recent_count={len(read_recent)}\n"
        + f"- sent_pending={status_count['pending']} sent_delivered={status_count['delivered']} "
        + f"sent_handled={status_count['handled']} sent_failed={status_count['failed']}\n"
        + "\n[INBOX UNREAD]\n"
        + (
            "\n".join(
                [
                    f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f}: {x.content}"
                    for x in unread
                ]
            )
            if unread
            else "- (none)"
        )
        + "\n\n[INBOX READ RECENT]\n"
        + (
            "\n".join(
                [
                    f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f}"
                    for x in read_recent
                ]
            )
            if read_recent
            else "- (none)"
        )
        + "\n\n[SENT RECEIPTS]\n"
        + (
            "\n".join(
                [
                    f"- [title={r.title}][to={r.to_agent_id}][status={r.status.value}] mid={r.message_id} updated={r.updated_at:.3f}"
                    for r in receipts[: max(1, budget)]
                ]
            )
            if receipts
            else "- (none)"
        )
    )
    return text


def ack_handled(project_id: str, event_ids: list[str], agent_id: str = ""):
    handled = mark_inbox_events_handled(project_id, event_ids)
    for item in handled:
        updated = update_status_by_message_id(
            project_id=project_id,
            message_id=item.event_id,
            status=OutboxReceiptStatus.HANDLED,
        )
        for rec in updated:
            record_intent(
                intent_from_outbox_status(
                    project_id=project_id,
                    agent_id=rec.from_agent_id,
                    to_agent_id=rec.to_agent_id,
                    title=rec.title,
                    message_id=rec.message_id,
                    status=rec.status.value,
                )
            )
    if not agent_id:
        return
    ids = [str(x.event_id) for x in handled]
    if not ids:
        return
    record_intent(
        intent_from_inbox_read(
            project_id=project_id,
            agent_id=agent_id,
            delivered_ids=ids,
            count=len(ids),
        )
    )


def has_pending(project_id: str, agent_id: str) -> bool:
    return has_pending_inbox_events(project_id, agent_id)


def list_events(
    project_id: str,
    agent_id: str | None,
    state: InboxMessageState | None,
    limit: int,
) -> list[InboxEvent]:
    return list_inbox_events(project_id, agent_id=agent_id, state=state, limit=limit)


def list_outbox_receipts(
    project_id: str,
    from_agent_id: str = "",
    to_agent_id: str = "",
    status: str = "",
    limit: int = 100,
) -> list[OutboxReceipt]:
    return list_receipts(
        project_id=project_id,
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        status=status,
        limit=limit,
    )
