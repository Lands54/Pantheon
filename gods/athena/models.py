"""Athena flow contracts for project-level multi-agent process orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowDefinition:
    key: str
    title: str
    stages: list[str]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "stages": list(self.stages or []),
            "description": self.description,
        }


@dataclass
class FlowRun:
    run_id: str
    project_id: str
    flow_key: str
    title: str
    participants: list[str]
    status: str = "active"  # active | paused | completed | aborted
    stages: list[str] = field(default_factory=list)
    stage_index: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    started_by: str = "human.overseer"

    @property
    def current_stage(self) -> str:
        if 0 <= int(self.stage_index) < len(self.stages):
            return str(self.stages[int(self.stage_index)])
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "flow_key": self.flow_key,
            "title": self.title,
            "participants": list(self.participants or []),
            "status": self.status,
            "stages": list(self.stages or []),
            "stage_index": int(self.stage_index),
            "current_stage": self.current_stage,
            "config": dict(self.config or {}),
            "created_at": float(self.created_at or 0.0),
            "updated_at": float(self.updated_at or 0.0),
            "started_by": self.started_by,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any] | None) -> "FlowRun":
        row = dict(row or {})
        return cls(
            run_id=str(row.get("run_id", "") or ""),
            project_id=str(row.get("project_id", "") or ""),
            flow_key=str(row.get("flow_key", "") or ""),
            title=str(row.get("title", "") or ""),
            participants=[str(x).strip() for x in list(row.get("participants", []) or []) if str(x).strip()],
            status=str(row.get("status", "active") or "active"),
            stages=[str(x).strip() for x in list(row.get("stages", []) or []) if str(x).strip()],
            stage_index=max(0, int(row.get("stage_index", 0) or 0)),
            config=dict(row.get("config", {}) or {}),
            created_at=float(row.get("created_at", 0.0) or 0.0),
            updated_at=float(row.get("updated_at", 0.0) or 0.0),
            started_by=str(row.get("started_by", "human.overseer") or "human.overseer"),
        )
