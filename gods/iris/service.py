"""Iris service orchestration for unified mail-event delivery."""
from __future__ import annotations

from gods.iris.models import MailEventState
from gods.iris.outbox_models import OutboxReceipt, OutboxReceiptStatus
from gods.iris.outbox_store import create_receipt, list_receipts, update_status_by_message_id
from gods.iris.store import (
    deliver_mailbox_events,
    enqueue_mail_event,
    has_pending_mailbox_events,
    list_mailbox_events,
    mark_mailbox_events_handled,
)
from gods.mnemosyne import load_memory_policy, record_intent, MemoryIntent
from gods.mnemosyne.facade import (
    intent_from_mailbox_section,
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_inbox_summary,
    intent_from_outbox_status,
    record_inbox_digest,
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
    attachments: list[str] | None = None,
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
        attachments=attachments,
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
            content=content,
            attachments=list(event.attachments or []),
            payload=event.payload,
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
            attachments_count=len(list(event.attachments or [])),
        )
    )
    return {
        "mail_event_id": event.event_id,
        "title": title,
        "outbox_receipt_id": receipt.receipt_id,
        "outbox_status": receipt.status.value,
        "attachments_count": len(list(event.attachments or [])),
    }


def fetch_mailbox_intents(
    project_id: str,
    agent_id: str,
    budget: int,
    preferred_event_ids: list[str] | None = None,
) -> list[MemoryIntent]:
    """
    Fetches mailbox events (inbox + outbox status) and summaries as structured MemoryIntent objects.
    """
    intents: list[MemoryIntent] = []
    
    # 1. Fetch and Deliver New Events
    preferred = [str(x).strip() for x in (preferred_event_ids or []) if str(x).strip()]
    events = deliver_mailbox_events(project_id, agent_id, budget, preferred_event_ids=preferred or None)
    delivered_ids = []
    
    for item in events:
        delivered_ids.append(item.event_id)
        # Update status to DELIVERED
        updated = update_status_by_message_id(
            project_id=project_id,
            message_id=item.event_id,
            status=OutboxReceiptStatus.DELIVERED,
        )
        # Record outbox status updates for sender awareness
        for rec in updated:
            record_intent(
                intent_from_outbox_status(
                    project_id=project_id,
                    agent_id=rec.from_agent_id,
                    to_agent_id=rec.to_agent_id,
                    title=rec.title,
                    message_id=rec.message_id,
                    status=rec.status.value,
                    attachments_count=0,
                )
            )

        # Create Inbox Received Intent
        intents.append(
            intent_from_inbox_received(
                project_id=project_id,
                agent_id=agent_id,
                title=item.title,
                sender=item.sender,
                message_id=item.event_id,
                content=item.content,
                attachments=list(item.attachments or []),
                payload=item.payload,
                msg_type=item.msg_type,
                intent_key=_resolve_inbox_received_intent_key(project_id, item.msg_type),
            )
        )

    # 2. Inbox Statistics & Context
    read_recent = list_mailbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=MailEventState.HANDLED,
        limit=max(1, min(budget, 10)),
    )
    receipts = list_receipts(project_id=project_id, from_agent_id=agent_id, limit=max(1, min(budget * 3, 50)))
    
    unread_count = len(
        list_mailbox_events(project_id=project_id, agent_id=agent_id, state=MailEventState.QUEUED, limit=1000)
    ) + len(
        list_mailbox_events(project_id=project_id, agent_id=agent_id, state=MailEventState.DEFERRED, limit=1000)
    )
    
    status_count = {"pending": 0, "delivered": 0, "handled": 0, "failed": 0}
    for r in receipts:
        if r.status.value in status_count:
            status_count[r.status.value] += 1
            
    summary_data = {
        "unread_count": unread_count,
        "read_recent_count": len(read_recent),
        "sent_stats": status_count,
        "delivered_ids": delivered_ids
    }
    intents.insert(0, intent_from_inbox_summary(project_id, agent_id, summary_data))

    summary_rows = [
        (
            f"- unread_count={unread_count} read_recent_count={len(read_recent)} "
            f"sent_pending={status_count['pending']} sent_delivered={status_count['delivered']} "
            f"sent_handled={status_count['handled']} sent_failed={status_count['failed']}"
        )
    ]
    read_rows = [
        f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f}"
        for x in read_recent[-10:]
    ]
    send_rows = [
        f"- [title={r.title}][to={r.to_agent_id}][status={r.status.value}] mid={r.message_id} updated={r.updated_at:.3f}"
        for r in receipts[:20]
    ]
    inbox_unread_rows = [
        f"- [title={x.title}][from={x.sender}] id={x.event_id} msg_type={x.msg_type} "
        f"attachments={len(list(x.attachments or []))}"
        for x in events
    ]
    section_intents = [
        intent_from_mailbox_section(project_id, agent_id, "summary", summary_rows),
        intent_from_mailbox_section(project_id, agent_id, "recent_read", read_rows),
        intent_from_mailbox_section(project_id, agent_id, "recent_send", send_rows),
        intent_from_mailbox_section(project_id, agent_id, "inbox_unread", inbox_unread_rows),
    ]
    intents = section_intents + intents
    
    return intents


def fetch_inbox_context(project_id: str, agent_id: str, budget: int) -> tuple[str, list[str]]:
    events = deliver_mailbox_events(project_id, agent_id, budget)
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
                    attachments_count=0,
                )
            )

    lines = []
    for item in events:
        aid_list = list(item.attachments or [])
        suffix = ""
        if aid_list:
            suffix = f" [attachments={len(aid_list)} ids={','.join(aid_list[:5])}]"
        lines.append(
            f"- [title={item.title}][from={item.sender}][status={item.state.value}] at={item.created_at:.3f} "
            f"id={item.event_id}{suffix}: {item.content}"
        )
    ids = [item.event_id for item in events]
    read_recent = list_mailbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=MailEventState.HANDLED,
        limit=max(1, min(budget, 10)),
    )
    receipts = list_receipts(project_id=project_id, from_agent_id=agent_id, limit=max(1, min(budget * 3, 50)))
    unread_count = len(
        list_mailbox_events(project_id=project_id, agent_id=agent_id, state=MailEventState.QUEUED, limit=1000)
    ) + len(
        list_mailbox_events(project_id=project_id, agent_id=agent_id, state=MailEventState.DEFERRED, limit=1000)
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
    unread = list_mailbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=MailEventState.QUEUED,
        limit=budget,
    ) + list_mailbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=MailEventState.DEFERRED,
        limit=budget,
    )
    unread.sort(key=lambda x: x.created_at)
    unread = unread[-budget:]
    read_recent = list_mailbox_events(
        project_id=project_id,
        agent_id=agent_id,
        state=MailEventState.HANDLED,
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
    )

    unread_lines = []
    for x in unread:
        unread_lines.append(
            f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f} "
            f"[attachments={len(list(x.attachments or []))}]: {x.content}"
        )

    text += ("\n".join(unread_lines) if unread_lines else "- (none)")
    text += "\n\n[INBOX READ RECENT]\n"
    text += (
        "\n".join(
            [
                f"- [title={x.title}][from={x.sender}][status={x.state.value}] id={x.event_id} at={x.created_at:.3f}"
                for x in read_recent
            ]
        )
        if read_recent
        else "- (none)"
    )
    text += "\n\n[SENT RECEIPTS]\n"
    text += (
        "\n".join(
            [
                f"- [title={r.title}][to={r.to_agent_id}][status={r.status.value}] mid={r.message_id} updated={r.updated_at:.3f}"
                for r in receipts[: max(1, budget)]
            ]
        )
        if receipts
        else "- (none)"
    )

    return text


def ack_handled(project_id: str, event_ids: list[str], agent_id: str = ""):
    handled = mark_mailbox_events_handled(project_id, event_ids)
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
                    attachments_count=0,
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
    return has_pending_mailbox_events(project_id, agent_id)


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
