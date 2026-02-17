"""Iris service orchestration for unified mail-event delivery."""
from __future__ import annotations

from typing import Any

from gods.iris.models import InboxEvent, InboxMessageState, MailEventState
from gods.iris.outbox_models import OutboxReceipt, OutboxReceiptStatus
from gods.iris.outbox_store import create_receipt, list_receipts, update_status_by_message_id
from gods.iris.store import (
    enqueue_mail_event,
    has_pending_inbox_events,
    list_inbox_events,
    list_mail_events,
    mark_mail_done,
    mark_mail_failed_or_requeue,
    mark_mail_processing,
    pick_next_mail_event,
    reclaim_stale_mail_processing,
    retry_mail_event,
    mark_inbox_events_handled,
    take_deliverable_inbox_events,
)
from gods.mnemosyne import load_memory_policy, record_intent
from gods.mnemosyne.facade import (
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_outbox_status,
)

def _resolve_inbox_received_intent_key(project_id: str, msg_type: str) -> str:
    mt = str(msg_type or "").strip().lower()
    preferred = {
        "contract_commit_notice": "inbox.notice.contract_commit_notice",
        "contract_fully_committed": "inbox.notice.contract_fully_committed",
    }.get(mt, "inbox.received.unread")
    if preferred == "inbox.received.unread":
        return preferred
    try:
        policy = load_memory_policy(project_id)
        if preferred in policy:
            return preferred
    except Exception:
        pass
    return "inbox.received.unread"


def set_wake_enqueue(_func):
    """Legacy no-op after single-source switch."""
    return None


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
    event = enqueue_mail_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type="mail_event",
        priority=int(pulse_priority),
        payload={"reason": "mail_event", "source": "iris"},
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
            msg_type=msg_type,
            intent_key=_resolve_inbox_received_intent_key(project_id, msg_type),
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
    woke = False
    if trigger_pulse:
        try:
            # Cross-domain via facade only: wake target worker for newly queued mail event.
            from gods.angelia import facade as angelia_facade

            angelia_facade.wake_agent(project_id=project_id, agent_id=agent_id)
            woke = True
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
        "mail_event_id": event.event_id,
        "title": title,
        "outbox_receipt_id": receipt.receipt_id,
        "outbox_status": receipt.status.value,
        "wakeup_sent": bool(woke),
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


def pick_mail_event(project_id: str, agent_id: str, now: float, cooldown_until: float, preempt_types: set[str]):
    return pick_next_mail_event(project_id, agent_id, now, cooldown_until, preempt_types)


def mark_processing(project_id: str, event_id: str) -> bool:
    return mark_mail_processing(project_id, event_id)


def mark_done(project_id: str, event_id: str) -> bool:
    return mark_mail_done(project_id, event_id)


def mark_failed_or_requeue(project_id: str, event_id: str, error_code: str, error_message: str, retry_delay_sec: int = 0) -> str:
    return mark_mail_failed_or_requeue(project_id, event_id, error_code, error_message, retry_delay_sec)


def reclaim_stale_processing(project_id: str, timeout_sec: int) -> int:
    return reclaim_stale_mail_processing(project_id, timeout_sec)


def retry_event(project_id: str, event_id: str) -> bool:
    return retry_mail_event(project_id, event_id)


def list_mail_runtime_events(
    project_id: str,
    agent_id: str = "",
    state: str = "",
    event_type: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    st = MailEventState(state) if state else None
    return [
        row.to_dict()
        for row in list_mail_events(
            project_id=project_id,
            agent_id=agent_id,
            state=st,
            event_type=event_type,
            limit=limit,
        )
    ]

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
