"""Public facade for iris mailbox domain operations."""
from __future__ import annotations

from gods.iris.service import (
    ack_handled,
    build_inbox_overview,
    enqueue_message,
    fetch_inbox_context,
    has_pending,
    list_outbox_receipts,
)

__all__ = [
    "enqueue_message",
    "fetch_inbox_context",
    "ack_handled",
    "has_pending",
    "list_outbox_receipts",
    "build_inbox_overview",
]
