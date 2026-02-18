"""Public facade for mnemosyne domain operations."""
from __future__ import annotations

from typing import Any

from gods.mnemosyne import VALID_VAULTS, list_entries, read_entry, write_entry
from gods.mnemosyne.compaction import load_chronicle_for_context
from gods.mnemosyne.context_materials import (
    read_profile,
    read_task_state,
    list_observations,
    observations_path,
    chronicle_path,
    load_agent_directives,
    ensure_agent_memory_seeded,
)
from gods.mnemosyne.context_reports import latest_context_report, list_context_reports, record_context_report
from gods.mnemosyne.contracts import ObservationRecord
from gods.mnemosyne.journal import inbox_digest_path, record_inbox_digest, record_observation
from gods.mnemosyne.memory import render_intent_for_llm_context
from gods.mnemosyne.policy_registry import default_memory_policy, required_intent_keys
from gods.mnemosyne.state_window import load_state_window, save_state_window
from gods.mnemosyne.artifacts import (
    put_artifact_text,
    put_artifact_bytes,
    head_artifact,
    get_artifact_bytes,
    materialize_artifact,
    list_artifacts,
    is_valid_artifact_id,
    grant_artifact_access,
    list_artifact_grants,
)
from gods.mnemosyne.intent_builders import (
    intent_from_angelia_event,
    intent_from_mailbox_section,
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_inbox_summary,
    intent_from_outbox_status,
    intent_from_tool_result,
)


def render_intents_for_llm(intents: list[Any]) -> list[str]:
    lines: list[str] = []
    for intent in list(intents or []):
        try:
            rendered = render_intent_for_llm_context(intent)
        except Exception:
            rendered = None
        if rendered:
            lines.append(str(rendered))
    return lines


__all__ = [
    "VALID_VAULTS",
    "write_entry",
    "list_entries",
    "read_entry",
    "intent_from_tool_result",
    "intent_from_angelia_event",
    "intent_from_mailbox_section",
    "intent_from_inbox_read",
    "intent_from_inbox_received",
    "intent_from_inbox_summary",
    "intent_from_outbox_status",
    "render_intents_for_llm",
    "load_chronicle_for_context",
    "read_profile",
    "read_task_state",
    "list_observations",
    "observations_path",
    "chronicle_path",
    "load_agent_directives",
    "ensure_agent_memory_seeded",
    "latest_context_report",
    "list_context_reports",
    "record_context_report",
    "ObservationRecord",
    "record_observation",
    "record_inbox_digest",
    "inbox_digest_path",
    "load_state_window",
    "save_state_window",
    "default_memory_policy",
    "required_intent_keys",
    "put_artifact_text",
    "put_artifact_bytes",
    "head_artifact",
    "get_artifact_bytes",
    "materialize_artifact",
    "list_artifacts",
    "is_valid_artifact_id",
    "grant_artifact_access",
    "list_artifact_grants",
]
