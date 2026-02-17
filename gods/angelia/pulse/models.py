"""Pulse queue event models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PulseEventStatus(str, Enum):
    QUEUED = "queued"
    PICKED = "picked"
    DONE = "done"
    DROPPED = "dropped"


@dataclass
class PulseEvent:
    """Single pulse event persisted in project runtime store."""

    event_id: str
    project_id: str
    agent_id: str
    event_type: str
    priority: int
    created_at: float
    status: PulseEventStatus = PulseEventStatus.QUEUED
    payload: dict[str, Any] | None = None
    picked_at: float | None = None
    done_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "priority": int(self.priority),
            "created_at": float(self.created_at),
            "status": self.status.value,
            "payload": self.payload or {},
            "picked_at": self.picked_at,
            "done_at": self.done_at,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "PulseEvent":
        return cls(
            event_id=str(row.get("event_id", "")),
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            event_type=str(row.get("event_type", "timer")),
            priority=int(row.get("priority", 0)),
            created_at=float(row.get("created_at", 0.0)),
            status=PulseEventStatus(str(row.get("status", PulseEventStatus.QUEUED.value))),
            payload=row.get("payload") or {},
            picked_at=(float(row["picked_at"]) if row.get("picked_at") is not None else None),
            done_at=(float(row["done_at"]) if row.get("done_at") is not None else None),
        )
