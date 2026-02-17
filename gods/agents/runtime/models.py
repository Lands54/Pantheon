"""LangGraph runtime state model for agent execution."""
from __future__ import annotations

from typing import Any, TypedDict

from gods.mnemosyne import MemoryIntent


class RuntimeState(TypedDict, total=False):
    project_id: str
    agent_id: str
    strategy: str
    messages: list[Any]
    next_step: str
    abstained: list[str]
    context: str
    triggers: list[MemoryIntent]
    mailbox: list[MemoryIntent]
    tool_calls: list[dict[str, Any]]
    tool_results: list[str]
    pulse_meta: dict[str, Any]
    loop_count: int
    max_rounds: int
    llm_messages_buffer: list[Any]
    finalize_control: dict[str, Any]
    route: str
