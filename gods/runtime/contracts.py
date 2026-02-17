"""Runtime facade contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetachSubmitPayload:
    project_id: str
    agent_id: str
    command: str
