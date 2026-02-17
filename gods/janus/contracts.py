"""Janus facade contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JanusContextQuery:
    project_id: str
    agent_id: str
    limit: int = 20
