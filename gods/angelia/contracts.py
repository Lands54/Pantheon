"""Angelia facade contracts."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AngeliaEnqueueResult:
    project_id: str
    event_id: str
    state: str
    queued_at: float
    event: dict = field(default_factory=dict)
