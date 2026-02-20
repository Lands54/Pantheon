"""Janus context models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskStateCard:
    objective: str
    plan: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass
class ContextBuildRequest:
    project_id: str
    agent_id: str
    state: dict[str, Any]
    directives: str
    local_memory: str
    inbox_hint: str
    phase_block: str = ""
    phase_name: str = ""
    tools_desc: str = ""
    context_materials: Any = None
    agent: Any = None
    context_cfg: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextBuildResult:
    strategy_used: str
    system_blocks: list[str]
    token_usage: dict[str, int]
    preview: dict[str, Any] = field(default_factory=dict)
