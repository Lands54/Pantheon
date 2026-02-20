"""Public facade for iris mailbox domain operations."""
from __future__ import annotations

from gods.iris.service import (
    ack_handled,
    build_inbox_overview,
    enqueue_message,
    get_mailbox_glance,
    fetch_inbox_context,
    has_pending,
    list_outbox_receipts,
    mark_as_delivered,
)

__all__ = [
    "enqueue_message",
    "get_mailbox_glance",
    "fetch_inbox_context",
    "ack_handled",
    "has_pending",
    "list_outbox_receipts",
    "build_inbox_overview",
    "mark_as_delivered",
]
