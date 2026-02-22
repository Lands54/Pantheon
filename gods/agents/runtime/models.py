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
    # mailbox is unified message-domain context and includes inbox + outbox intents.
    mailbox: list[MemoryIntent]
    tool_calls: list[dict[str, Any]]
    tool_results: list[str]
    pulse_meta: dict[str, Any]
    loop_count: int
    max_rounds: int
    llm_messages_buffer: list[Any]
    finalize_control: dict[str, Any]
    route: str
    # Metis envelope is canonical strategy material source.
    __metis_envelope: Any
    __metis_refresh_mode: str
    __metis_refresh_seq: int
    # Pulse lifecycle keys injected by Angelia worker / engine.
    # These MUST be declared so LangGraph preserves them across node transitions.
    __pulse_meta: dict[str, Any]
    __chaos_synced_seq: int
    __inbox_delivered_ids: list[str]
