"""Angelia event and runtime models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AngeliaEventState(str, Enum):
    QUEUED = "queued"
    PICKED = "picked"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    HANDLED = "handled"
    DONE = "done"
    FAILED = "failed"
    DEFERRED = "deferred"
    DEAD = "dead"


class AgentRunState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COOLDOWN = "cooldown"
    ERROR_BACKOFF = "error_backoff"
    STOPPED = "stopped"


@dataclass
class AngeliaEvent:
    event_id: str
    project_id: str
    agent_id: str
    event_type: str
    priority: int
    state: AngeliaEventState
    payload: dict[str, Any]
    dedupe_key: str = ""
    attempt: int = 0
    max_attempts: int = 3
    created_at: float = 0.0
    available_at: float = 0.0
    picked_at: float | None = None
    done_at: float | None = None
    error_code: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "priority": int(self.priority),
            "state": self.state.value,
            "payload": self.payload or {},
            "dedupe_key": self.dedupe_key,
            "attempt": int(self.attempt),
            "max_attempts": int(self.max_attempts),
            "created_at": float(self.created_at),
            "available_at": float(self.available_at),
            "picked_at": self.picked_at,
            "done_at": self.done_at,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "AngeliaEvent":
        return cls(
            event_id=str(row.get("event_id", "")),
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            event_type=str(row.get("event_type", "system")),
            priority=int(row.get("priority", 0)),
            state=AngeliaEventState(str(row.get("state", AngeliaEventState.QUEUED.value))),
            payload=row.get("payload") or {},
            dedupe_key=str(row.get("dedupe_key", "")),
            attempt=int(row.get("attempt", 0)),
            max_attempts=int(row.get("max_attempts", 3)),
            created_at=float(row.get("created_at", 0.0)),
            available_at=float(row.get("available_at", row.get("created_at", 0.0))),
            picked_at=(float(row["picked_at"]) if row.get("picked_at") is not None else None),
            done_at=(float(row["done_at"]) if row.get("done_at") is not None else None),
            error_code=str(row.get("error_code", "")),
            error_message=str(row.get("error_message", "")),
        )


@dataclass
class AgentRuntimeStatus:
    project_id: str
    agent_id: str
    run_state: AgentRunState = AgentRunState.IDLE
    current_event_id: str = ""
    current_event_type: str = ""
    last_wake_at: float = 0.0
    cooldown_until: float = 0.0
    backoff_until: float = 0.0
    last_error: str = ""
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "run_state": self.run_state.value,
            "current_event_id": self.current_event_id,
            "current_event_type": self.current_event_type,
            "last_wake_at": float(self.last_wake_at),
            "cooldown_until": float(self.cooldown_until),
            "backoff_until": float(self.backoff_until),
            "last_error": self.last_error,
            "updated_at": float(self.updated_at),
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "AgentRuntimeStatus":
        return cls(
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            run_state=AgentRunState(str(row.get("run_state", AgentRunState.IDLE.value))),
            current_event_id=str(row.get("current_event_id", "")),
            current_event_type=str(row.get("current_event_type", "")),
            last_wake_at=float(row.get("last_wake_at", 0.0)),
            cooldown_until=float(row.get("cooldown_until", 0.0)),
            backoff_until=float(row.get("backoff_until", 0.0)),
            last_error=str(row.get("last_error", "")),
            updated_at=float(row.get("updated_at", 0.0)),
        )
