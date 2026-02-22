"""Public facade for mnemosyne domain operations."""
from __future__ import annotations

from gods.mnemosyne import (
    VALID_VAULTS,
    MemoryIntent,
    list_entries,
    read_entry,
    write_entry,
    record_intent,
    fetch_intents_between,
)
from gods.mnemosyne.compaction import load_chronicle_for_context
from gods.mnemosyne.context_materials import (
    read_profile,
    read_task_state,
    chronicle_path,
    load_agent_directives,
    ensure_agent_memory_seeded,
)
from gods.mnemosyne.context_reports import latest_context_report, list_context_reports, record_context_report
from gods.mnemosyne.journal import inbox_digest_path, record_inbox_digest
from gods.mnemosyne.context_index import (
    list_context_index_entries,
    list_context_index_texts,
    rebuild_context_index_from_intents,
)
from gods.mnemosyne.chronicle_index import (
    list_chronicle_index_entries,
    list_chronicle_index_texts,
    rebuild_chronicle_markdown_from_index,
)
from gods.mnemosyne.policy_registry import default_memory_policy, required_intent_keys
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
from gods.mnemosyne.janus_snapshot import (
    CHAOS_CARD_BUCKET_KEYS,
    load_janus_snapshot,
    save_janus_snapshot,
    build_cards_from_intents,
    build_cards_from_intent_views,
    estimate_cards_tokens,
    latest_intent_seq,
    record_snapshot_compression,
    list_snapshot_compressions,
    list_derived_cards,
    validate_context_card,
    validate_card_buckets,
)
from gods.mnemosyne.pulse_ledger import (
    PulseIntegrityReport,
    append_pulse_entry,
    append_pulse_entries,
    discard_incomplete_frames,
    list_pulse_entries,
    group_pulses,
    trim_truncated_head,
    validate_pulse_integrity,
)
from gods.mnemosyne.intent_builders import (
    intent_from_angelia_event,
    intent_from_mailbox_section,
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_inbox_summary,
    intent_from_outbox_status,
    intent_from_tool_call,
    intent_from_tool_result,
    intent_from_janus_compaction_base,
    intent_from_pulse_finish,
    intent_from_pulse_start,
)
from gods.mnemosyne.intent_schema_registry import validate_intent_contract


def memory_intent_from_row(row: dict[str, Any]) -> MemoryIntent | None:
    if not isinstance(row, dict):
        return None
    try:
        return MemoryIntent(
            intent_key=str(row.get("intent_key", "") or "").strip(),
            project_id=str(row.get("project_id", "") or "").strip(),
            agent_id=str(row.get("agent_id", "") or "").strip(),
            source_kind=str(row.get("source_kind", "agent") or "agent"),  # type: ignore[arg-type]
            payload=dict(row.get("payload", {}) or {}),
            fallback_text=str(row.get("fallback_text", "") or ""),
            timestamp=float(row.get("timestamp", 0.0) or 0.0),
        )
    except Exception:
        return None


def render_intents_for_llm(intents: list[Any]) -> list[str]:
    lines: list[str] = []
    for intent in list(intents or []):
        text = str(getattr(intent, "fallback_text", "") or "").strip()
        if text:
            lines.append(text)
    return lines


def record_janus_compaction_base_intent(
    project_id: str,
    agent_id: str,
    summary: str,
    base_intent_seq: int,
    source_card_ids: list[str] | None = None,
) -> dict[str, Any]:
    intent = intent_from_janus_compaction_base(
        project_id=project_id,
        agent_id=agent_id,
        summary=summary,
        base_intent_seq=base_intent_seq,
        source_card_ids=source_card_ids or [],
    )
    return record_intent(intent)


__all__ = [
    "VALID_VAULTS",
    "write_entry",
    "list_entries",
    "read_entry",
    "intent_from_tool_result",
    "intent_from_tool_call",
    "intent_from_angelia_event",
    "intent_from_mailbox_section",
    "intent_from_inbox_read",
    "intent_from_inbox_received",
    "intent_from_inbox_summary",
    "intent_from_outbox_status",
    "intent_from_janus_compaction_base",
    "intent_from_pulse_start",
    "intent_from_pulse_finish",
    "record_janus_compaction_base_intent",
    "render_intents_for_llm",
    "load_chronicle_for_context",
    "read_profile",
    "read_task_state",
    "chronicle_path",
    "load_agent_directives",
    "ensure_agent_memory_seeded",
    "latest_context_report",
    "list_context_reports",
    "record_context_report",
    "list_context_index_entries",
    "list_context_index_texts",
    "rebuild_context_index_from_intents",
    "list_chronicle_index_entries",
    "list_chronicle_index_texts",
    "rebuild_chronicle_markdown_from_index",
    "record_inbox_digest",
    "inbox_digest_path",
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
    "load_janus_snapshot",
    "save_janus_snapshot",
    "build_cards_from_intents",
    "build_cards_from_intent_views",
    "estimate_cards_tokens",
    "latest_intent_seq",
    "record_snapshot_compression",
    "list_snapshot_compressions",
    "list_derived_cards",
    "CHAOS_CARD_BUCKET_KEYS",
    "validate_context_card",
    "validate_card_buckets",
    "fetch_intents_between",
    "append_pulse_entry",
    "append_pulse_entries",
    "discard_incomplete_frames",
    "list_pulse_entries",
    "group_pulses",
    "trim_truncated_head",
    "validate_pulse_integrity",
    "PulseIntegrityReport",
    "validate_intent_contract",
    "memory_intent_from_row",
]
