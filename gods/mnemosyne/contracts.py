"""Typed memory contracts for Mnemosyne."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MemorySourceKind = Literal["event", "tool", "agent", "phase", "llm", "inbox"]


@dataclass
class MemoryIntent:
    intent_key: str
    project_id: str
    agent_id: str
    source_kind: MemorySourceKind
    payload: dict[str, Any] = field(default_factory=dict)
    fallback_text: str = ""
    timestamp: float = 0.0


@dataclass
class ObservationRecord:
    project_id: str
    agent_id: str
    tool_name: str
    args_summary: str
    result_summary: str
    status: str
    timestamp: float


@dataclass
class MemorySinkPolicy:
    to_chronicle: bool
    to_runtime_log: bool
    to_llm_context: bool = False
    chronicle_template_key: str = ""
    runtime_log_template_key: str = ""
    llm_context_template_key: str = ""


@dataclass
class MemoryDecision:
    intent_key: str
    chronicle_written: bool
    runtime_log_written: bool
    text: str
    policy: MemorySinkPolicy
    llm_context_rendered: str | None = None
