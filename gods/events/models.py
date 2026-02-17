"""Unified event-bus models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import uuid


class EventState(str, Enum):
    QUEUED = "queued"
    PICKED = "picked"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class EventRecord:
    event_id: str
    project_id: str
    domain: str
    event_type: str
    state: EventState
    priority: int
    payload: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    max_attempts: int = 3
    dedupe_key: str = ""
    created_at: float = 0.0
    available_at: float = 0.0
    picked_at: float | None = None
    done_at: float | None = None
    error_code: str = ""
    error_message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        domain: str,
        event_type: str,
        priority: int,
        payload: dict[str, Any] | None = None,
        dedupe_key: str = "",
        max_attempts: int = 3,
        meta: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> "EventRecord":
        now = time.time()
        return cls(
            event_id=event_id or uuid.uuid4().hex,
            project_id=project_id,
            domain=domain,
            event_type=event_type,
            state=EventState.QUEUED,
            priority=int(priority),
            payload=payload or {},
            attempt=0,
            max_attempts=max(1, int(max_attempts)),
            dedupe_key=str(dedupe_key or ""),
            created_at=now,
            available_at=now,
            meta=meta or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "domain": self.domain,
            "event_type": self.event_type,
            "state": self.state.value,
            "priority": int(self.priority),
            "payload": self.payload or {},
            "attempt": int(self.attempt),
            "max_attempts": int(self.max_attempts),
            "dedupe_key": self.dedupe_key,
            "created_at": float(self.created_at),
            "available_at": float(self.available_at),
            "picked_at": self.picked_at,
            "done_at": self.done_at,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "meta": self.meta or {},
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "EventRecord":
        return cls(
            event_id=str(row.get("event_id", "")),
            project_id=str(row.get("project_id", "")),
            domain=str(row.get("domain", "unknown")),
            event_type=str(row.get("event_type", "unknown_event")),
            state=EventState(str(row.get("state", EventState.QUEUED.value))),
            priority=int(row.get("priority", 0)),
            payload=row.get("payload") or {},
            attempt=int(row.get("attempt", 0)),
            max_attempts=int(row.get("max_attempts", 3)),
            dedupe_key=str(row.get("dedupe_key", "")),
            created_at=float(row.get("created_at", 0.0)),
            available_at=float(row.get("available_at", row.get("created_at", 0.0))),
            picked_at=(float(row["picked_at"]) if row.get("picked_at") is not None else None),
            done_at=(float(row["done_at"]) if row.get("done_at") is not None else None),
            error_code=str(row.get("error_code", "")),
            error_message=str(row.get("error_message", "")),
            meta=row.get("meta") or {},
        )


@dataclass
class EventEnvelope:
    record: EventRecord
    stage: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "stage": self.stage,
            "extra": self.extra or {},
        }
