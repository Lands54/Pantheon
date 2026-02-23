"""Robert Rules core data models for sync council."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MeetingPhase = Literal["collecting", "draining", "in_session", "paused", "completed", "aborted"]
MotionState = Literal[
    "proposed",
    "seconded",
    "debating",
    "amendment_pending",
    "voting",
    "adopted",
    "rejected",
    "tabled",
    "withdrawn",
]
ActionType = Literal[
    "motion_submit",
    "motion_second",
    "debate_speak",
    "amend_submit",
    "amend_second",
    "procedural_call_question",
    "procedural_table_motion",
    "vote_cast",
    "reconsider_submit",
    "reconsider_second",
    "chair_override_pause",
    "chair_override_resume",
    "chair_override_terminate",
    "chair_override_skip_turn",
]


@dataclass
class MeetingState:
    schema_version: int = 2
    enabled: bool = False
    session_id: str = ""
    rules_profile: str = "roberts_core_v1"
    phase: str = "completed"
    title: str = ""
    content: str = ""
    agenda: list[dict[str, Any]] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    confirmed_agents: list[str] = field(default_factory=list)
    cycles_total: int = 0
    cycles_left: int = 0
    current_index: int = 0
    current_speaker: str = ""
    current_motion_id: str = ""
    motion_queue: list[dict[str, Any]] = field(default_factory=list)
    current_motion: dict[str, Any] = field(default_factory=dict)
    floor_state: str = "open"
    vote_state: dict[str, Any] = field(default_factory=dict)
    deferred_event_ids: list[str] = field(default_factory=list)
    resolution_ids: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    last_transition_at: float = 0.0
    last_transition_reason: str = ""
    initiator: str = "human.overseer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "enabled": bool(self.enabled),
            "session_id": str(self.session_id),
            "rules_profile": str(self.rules_profile),
            "phase": str(self.phase),
            "title": str(self.title),
            "content": str(self.content),
            "agenda": list(self.agenda or []),
            "participants": list(self.participants or []),
            "confirmed_agents": list(self.confirmed_agents or []),
            "cycles_total": int(self.cycles_total),
            "cycles_left": int(self.cycles_left),
            "current_index": int(self.current_index),
            "current_speaker": str(self.current_speaker),
            "current_motion_id": str(self.current_motion_id),
            "motion_queue": list(self.motion_queue or []),
            "current_motion": dict(self.current_motion or {}),
            "floor_state": str(self.floor_state),
            "vote_state": dict(self.vote_state or {}),
            "deferred_event_ids": list(self.deferred_event_ids or []),
            "resolution_ids": list(self.resolution_ids or []),
            "created_at": float(self.created_at),
            "updated_at": float(self.updated_at),
            "last_transition_at": float(self.last_transition_at),
            "last_transition_reason": str(self.last_transition_reason),
            "initiator": str(self.initiator),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MeetingState":
        row = dict(data or {})
        return cls(
            schema_version=int(row.get("schema_version", 2) or 2),
            enabled=bool(row.get("enabled", False)),
            session_id=str(row.get("session_id", "") or ""),
            rules_profile=str(row.get("rules_profile", "roberts_core_v1") or "roberts_core_v1"),
            phase=str(row.get("phase", "completed") or "completed"),
            title=str(row.get("title", "") or ""),
            content=str(row.get("content", "") or ""),
            agenda=list(row.get("agenda", []) or []),
            participants=list(row.get("participants", []) or []),
            confirmed_agents=list(row.get("confirmed_agents", []) or []),
            cycles_total=int(row.get("cycles_total", 0) or 0),
            cycles_left=int(row.get("cycles_left", 0) or 0),
            current_index=int(row.get("current_index", 0) or 0),
            current_speaker=str(row.get("current_speaker", "") or ""),
            current_motion_id=str(row.get("current_motion_id", "") or ""),
            motion_queue=list(row.get("motion_queue", []) or []),
            current_motion=dict(row.get("current_motion", {}) or {}),
            floor_state=str(row.get("floor_state", "open") or "open"),
            vote_state=dict(row.get("vote_state", {}) or {}),
            deferred_event_ids=list(row.get("deferred_event_ids", []) or []),
            resolution_ids=list(row.get("resolution_ids", []) or []),
            created_at=float(row.get("created_at", 0.0) or 0.0),
            updated_at=float(row.get("updated_at", 0.0) or 0.0),
            last_transition_at=float(row.get("last_transition_at", 0.0) or 0.0),
            last_transition_reason=str(row.get("last_transition_reason", "") or ""),
            initiator=str(row.get("initiator", "human.overseer") or "human.overseer"),
        )


@dataclass
class PickGateDecision:
    allowed: bool
    reason: str
    defer: bool = False
