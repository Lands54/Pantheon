"""Mnemosyne artifact namespace contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ArtifactScope = Literal["global", "project", "agent"]


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    scope: ArtifactScope
    project_id: str
    owner_agent_id: str
    mime: str
    size: int
    sha256: str
    created_at: float


@dataclass(frozen=True)
class ArtifactACLDecision:
    allowed: bool
    reason: str = ""

