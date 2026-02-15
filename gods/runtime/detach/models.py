"""Detach runtime models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DetachStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    LOST = "lost"


@dataclass
class DetachJob:
    job_id: str
    project_id: str
    agent_id: str
    command: str
    created_at: float
    started_at: float | None = None
    ended_at: float | None = None
    status: DetachStatus = DetachStatus.QUEUED
    pid_or_container_exec_ref: str = ""
    stop_reason: str = ""
    exit_code: int | None = None
    log_path: str = ""
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "command": self.command,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status.value,
            "pid_or_container_exec_ref": self.pid_or_container_exec_ref,
            "stop_reason": self.stop_reason,
            "exit_code": self.exit_code,
            "log_path": self.log_path,
            "meta": self.meta or {},
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "DetachJob":
        return cls(
            job_id=str(row.get("job_id", "")),
            project_id=str(row.get("project_id", "")),
            agent_id=str(row.get("agent_id", "")),
            command=str(row.get("command", "")),
            created_at=float(row.get("created_at", 0.0)),
            started_at=(float(row["started_at"]) if row.get("started_at") is not None else None),
            ended_at=(float(row["ended_at"]) if row.get("ended_at") is not None else None),
            status=DetachStatus(str(row.get("status", DetachStatus.QUEUED.value))),
            pid_or_container_exec_ref=str(row.get("pid_or_container_exec_ref", "")),
            stop_reason=str(row.get("stop_reason", "")),
            exit_code=(int(row["exit_code"]) if row.get("exit_code") is not None else None),
            log_path=str(row.get("log_path", "")),
            meta=row.get("meta") or {},
        )
