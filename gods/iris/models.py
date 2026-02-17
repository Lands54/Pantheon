"""Iris unified MailEvent models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MailEventState(str, Enum):
    """Unified lifecycle states for Iris single event source."""

    QUEUED = "queued"
    PICKED = "picked"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    HANDLED = "handled"
    DONE = "done"
    DEFERRED = "deferred"
    FAILED = "failed"
    DEAD = "dead"


class InboxMessageState(str, Enum):
    """Mailbox semantic states."""

    PENDING = MailEventState.QUEUED.value
    DELIVERED = MailEventState.DELIVERED.value
    DEFERRED = MailEventState.DEFERRED.value
    HANDLED = MailEventState.HANDLED.value


@dataclass
class MailEvent:
    """Single unified event record persisted in runtime JSONL."""

    event_id: str
    project_id: str
    agent_id: str
    event_type: str
    priority: int
    created_at: float
    state: MailEventState = MailEventState.QUEUED
    payload: dict[str, Any] | None = None
    sender: str = ""
    title: str = ""
    msg_type: str = "private"
    content: str = ""
    dedupe_key: str = ""
    attempt: int = 0
    max_attempts: int = 3
    available_at: float = 0.0
    picked_at: float | None = None
    delivered_at: float | None = None
    handled_at: float | None = None
    done_at: float | None = None
    error_code: str = ""
    error_message: str = ""
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "priority": int(self.priority),
            "created_at": float(self.created_at),
            "state": self.state.value,
            "payload": self.payload or {},
            "sender": self.sender,
            "title": self.title,
            "msg_type": self.msg_type,
            "content": self.content,
            "dedupe_key": self.dedupe_key,
            "attempt": int(self.attempt),
            "max_attempts": int(self.max_attempts),
            "available_at": float(self.available_at),
            "picked_at": self.picked_at,
            "delivered_at": self.delivered_at,
            "handled_at": self.handled_at,
            "done_at": self.done_at,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "meta": self.meta or {},
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "MailEvent":
        state_val = str(row.get("state", MailEventState.QUEUED.value))
        if state_val == "pending":
            state_val = MailEventState.QUEUED.value
        return cls(
            event_id=str(row.get("event_id", "")),
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            event_type=str(row.get("event_type", "mail_event")),
            priority=int(row.get("priority", 0)),
            created_at=float(row.get("created_at", 0.0)),
            state=MailEventState(state_val),
            payload=row.get("payload") or {},
            sender=str(row.get("sender", "")),
            title=str(row.get("title", "(untitled)") or "(untitled)"),
            msg_type=str(row.get("msg_type", "private")),
            content=str(row.get("content", "")),
            dedupe_key=str(row.get("dedupe_key", "")),
            attempt=int(row.get("attempt", 0)),
            max_attempts=int(row.get("max_attempts", 3)),
            available_at=float(row.get("available_at", row.get("created_at", 0.0))),
            picked_at=(float(row["picked_at"]) if row.get("picked_at") is not None else None),
            delivered_at=(float(row["delivered_at"]) if row.get("delivered_at") is not None else None),
            handled_at=(float(row["handled_at"]) if row.get("handled_at") is not None else None),
            done_at=(float(row["done_at"]) if row.get("done_at") is not None else None),
            error_code=str(row.get("error_code", "")),
            error_message=str(row.get("error_message", "")),
            meta=row.get("meta") or {},
        )


InboxEvent = MailEvent
