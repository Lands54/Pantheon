"""Inbox event models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InboxMessageState(str, Enum):
    """Lifecycle states for persisted inbox events."""

    PENDING = "pending"
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    HANDLED = "handled"


@dataclass
class InboxEvent:
    """Single inbox message event persisted in runtime JSONL."""

    event_id: str
    project_id: str
    agent_id: str
    sender: str
    title: str
    msg_type: str
    content: str
    created_at: float
    state: InboxMessageState = InboxMessageState.PENDING
    delivered_at: float | None = None
    handled_at: float | None = None
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "sender": self.sender,
            "title": self.title,
            "msg_type": self.msg_type,
            "content": self.content,
            "created_at": self.created_at,
            "state": self.state.value,
            "delivered_at": self.delivered_at,
            "handled_at": self.handled_at,
            "meta": self.meta or {},
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "InboxEvent":
        return cls(
            event_id=str(row.get("event_id", "")),
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            sender=str(row.get("sender", "")),
            title=str(row.get("title", "(untitled)") or "(untitled)"),
            msg_type=str(row.get("msg_type", "private")),
            content=str(row.get("content", "")),
            created_at=float(row.get("created_at", 0.0)),
            state=InboxMessageState(str(row.get("state", InboxMessageState.PENDING.value))),
            delivered_at=(float(row["delivered_at"]) if row.get("delivered_at") is not None else None),
            handled_at=(float(row["handled_at"]) if row.get("handled_at") is not None else None),
            meta=row.get("meta") or {},
        )
