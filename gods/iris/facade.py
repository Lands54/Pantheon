"""Public facade for iris domain operations."""
from __future__ import annotations

from gods.iris.models import InboxMessageState, MailEventState
from gods.iris.store import (
    enqueue_mail_event,
    list_mail_events,
    mark_mail_done,
    mark_mail_failed_or_requeue,
    mark_mail_handled,
    mark_mail_processing,
    pick_next_mail_event,
    reclaim_stale_mail_processing,
    retry_mail_event,
    enqueue_inbox_event,
    list_inbox_events,
    take_deliverable_inbox_events,
    transition_inbox_state,
)

from gods.iris import list_events, list_outbox_receipts
from gods.iris.service import (
    ack_handled,
    build_inbox_overview,
    enqueue_message,
    fetch_inbox_context,
    has_pending,
    list_mail_runtime_events,
    mark_done,
    mark_failed_or_requeue,
    mark_processing,
    pick_mail_event,
    reclaim_stale_processing,
    retry_event,
    set_wake_enqueue,
)


__all__ = [
    "enqueue_message",
    "fetch_inbox_context",
    "ack_handled",
    "has_pending",
    "pick_mail_event",
    "mark_processing",
    "mark_done",
    "mark_failed_or_requeue",
    "reclaim_stale_processing",
    "retry_event",
    "list_mail_runtime_events",
    "list_events",
    "list_outbox_receipts",
    "set_wake_enqueue",
    "build_inbox_overview",
    "MailEventState",
    "enqueue_mail_event",
    "list_mail_events",
    "pick_next_mail_event",
    "mark_mail_processing",
    "mark_mail_done",
    "mark_mail_failed_or_requeue",
    "reclaim_stale_mail_processing",
    "retry_mail_event",
    "mark_mail_handled",
    "take_deliverable_inbox_events",
    "InboxMessageState",
    "enqueue_inbox_event",
    "list_inbox_events",
    "transition_inbox_state",
]
