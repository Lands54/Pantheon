"""Iris facade contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IrisEnqueueMessageResult:
    inbox_event_id: str
    title: str
    outbox_receipt_id: str
    outbox_status: str
    pulse_event_id: str
