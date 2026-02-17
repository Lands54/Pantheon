"""Iris facade contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IrisEnqueueMessageResult:
    mail_event_id: str
    title: str
    outbox_receipt_id: str
    outbox_status: str
    wakeup_sent: bool
