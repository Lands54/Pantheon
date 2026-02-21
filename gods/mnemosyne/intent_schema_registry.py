"""Intent payload schema registry and observed-variable collector."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from gods.mnemosyne.intent_registry import is_registered_intent_key
from gods.paths import mnemosyne_dir

from gods.mnemosyne.semantics import semantics_service

BASE_VARS = ["project_id", "agent_id", "intent_key"]


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    if p.exists() and not p.is_dir():
        try:
            p.unlink()
        except Exception:
            pass
    p.mkdir(parents=True, exist_ok=True)
    return p


def observed_schema_path(project_id: str) -> Path:
    return _mn_root(project_id) / "intent_payload_observed.json"


def _read_observed(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_observed(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _type_name(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def observed_schema(project_id: str) -> dict[str, Any]:
    return _read_observed(observed_schema_path(project_id))


def observe_intent_payload(project_id: str, intent_key: str, payload: dict[str, Any] | None) -> None:
    key = str(intent_key or "").strip()
    if not key:
        return
    data = dict(payload or {})
    path = observed_schema_path(project_id)
    raw = _read_observed(path)
    row = raw.get(key)
    if not isinstance(row, dict):
        row = {"fields": {}, "count": 0, "updated_at": 0.0}
    fields = row.get("fields")
    if not isinstance(fields, dict):
        fields = {}
    row["count"] = int(row.get("count", 0) or 0) + 1
    row["updated_at"] = time.time()
    for k, v in data.items():
        fk = str(k).strip()
        if not fk:
            continue
        cur = fields.get(fk)
        if not isinstance(cur, dict):
            cur = {"types": [], "last_seen_value": ""}
        types = {str(x) for x in list(cur.get("types") or []) if str(x).strip()}
        types.add(_type_name(v))
        cur["types"] = sorted(types)
        cur["last_seen_value"] = str(v)
        fields[fk] = cur
    row["fields"] = fields
    raw[key] = row
    _write_observed(path, raw)


def schema_for_intent(intent_key: str) -> dict[str, list[str]]:
    k = str(intent_key or "").strip()
    return semantics_service.get_schema(k)


_TOOL_CALL_INTENT_RE = re.compile(r"^tool\.call\.([a-z][a-z0-9_]{0,63})$")
_TOOL_INTENT_RE = re.compile(r"^tool\.([a-z][a-z0-9_]{0,63})\.(ok|blocked|error)$")
_EVENT_INTENT_RE = re.compile(r"^event\.([a-z][a-z0-9_.-]{0,127})$")
_INBOX_SECTION_RE = re.compile(r"^inbox\.section\.(summary|recent_read|recent_send|inbox_unread)$")
_INBOX_NOTICE_RE = re.compile(r"^inbox\.notice\.[a-z][a-z0-9_.-]{0,127}$")
_OUTBOX_SENT_RE = re.compile(r"^outbox\.sent\.(pending|delivered|handled|failed)$")
_PHASE_RETRY_RE = re.compile(r"^phase\.retry\.(reason|act|observe)$")


def _expect_field_type(payload: dict[str, Any], key: str, expected: type, *, where: str) -> Any:
    if key not in payload:
        raise ValueError(f"invalid intent '{where}': missing payload.{key}")
    value = payload.get(key)
    if not isinstance(value, expected):
        raise ValueError(
            f"invalid intent '{where}': payload.{key} expected {expected.__name__}"
        )
    return value


import logging
logger = logging.getLogger(__name__)

def validate_intent_contract(intent_key: str, source_kind: str, payload: dict[str, Any] | None) -> None:
    try:
        _validate_intent_contract_strict(intent_key, source_kind, payload)
    except ValueError as e:
        logger.warning(f"Intent schema validation failed (softened): {e}")

def _validate_intent_contract_strict(intent_key: str, source_kind: str, payload: dict[str, Any] | None) -> None:
    """
    Phase-1 strict contract:
    - llm.response
    - tool.call.<tool_name>
    - tool.<tool_name>.<ok|blocked|error>
    Other intents remain permissive for incremental migration.
    """
    key = str(intent_key or "").strip()
    if not key:
        raise ValueError("invalid intent: intent_key is required")
    if not is_registered_intent_key(key):
        raise ValueError(
            f"invalid intent '{key}': unregistered intent_key under zero-compat strict mode"
        )
    data = payload or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid intent '{key}': payload must be object")

    if key == "llm.response":
        if str(source_kind or "").strip() != "llm":
            raise ValueError("invalid intent 'llm.response': source_kind must be 'llm'")
        allowed = {"phase", "content", "anchor_seq"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent 'llm.response': unsupported payload keys: {', '.join(unknown)}"
            )
        _expect_field_type(data, "phase", str, where=key)
        _expect_field_type(data, "content", str, where=key)
        if "anchor_seq" in data and data.get("anchor_seq") is not None:
            _expect_field_type(data, "anchor_seq", int, where=key)
        return

    if key.startswith("tool.call."):
        m = _TOOL_CALL_INTENT_RE.match(key)
        if not m:
            raise ValueError(
                f"invalid intent '{key}': expected format tool.call.<tool_name>"
            )
        if str(source_kind or "").strip() != "tool":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'tool'")
        tool_from_key = str(m.group(1))
        allowed = {"tool_name", "args", "call_id", "node"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        tool_name = _expect_field_type(data, "tool_name", str, where=key)
        _expect_field_type(data, "args", dict, where=key)
        _expect_field_type(data, "call_id", str, where=key)
        _expect_field_type(data, "node", str, where=key)
        if str(tool_name).strip() != tool_from_key:
            raise ValueError(
                f"invalid intent '{key}': payload.tool_name must equal '{tool_from_key}'"
            )
        return

    if key.startswith("tool."):
        m = _TOOL_INTENT_RE.match(key)
        if not m:
            raise ValueError(
                f"invalid intent '{key}': expected format tool.<tool_name>.<ok|blocked|error>"
            )
        if str(source_kind or "").strip() != "tool":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'tool'")
        tool_from_key = str(m.group(1))
        status_from_key = str(m.group(2))
        allowed = {"tool_name", "status", "args", "result", "result_compact", "call_id"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        tool_name = _expect_field_type(data, "tool_name", str, where=key)
        status = _expect_field_type(data, "status", str, where=key)
        _expect_field_type(data, "args", dict, where=key)
        if "call_id" in data:
            _expect_field_type(data, "call_id", str, where=key)
        _expect_field_type(data, "result", str, where=key)
        _expect_field_type(data, "result_compact", str, where=key)
        if str(tool_name).strip() != tool_from_key:
            raise ValueError(
                f"invalid intent '{key}': payload.tool_name must equal '{tool_from_key}'"
            )
        if str(status).strip().lower() != status_from_key:
            raise ValueError(
                f"invalid intent '{key}': payload.status must equal '{status_from_key}'"
            )
        return

    if key.startswith("event."):
        m = _EVENT_INTENT_RE.match(key)
        if not m:
            raise ValueError(f"invalid intent '{key}': malformed event intent key")
        if str(source_kind or "").strip() != "event":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'event'")
        # Event payload supports extensions (e.g. next_step/error) while enforcing core fields.
        _expect_field_type(data, "stage", str, where=key)
        _expect_field_type(data, "event_id", str, where=key)
        event_type = _expect_field_type(data, "event_type", str, where=key)
        _expect_field_type(data, "priority", int, where=key)
        _expect_field_type(data, "attempt", int, where=key)
        _expect_field_type(data, "max_attempts", int, where=key)
        _expect_field_type(data, "payload", dict, where=key)
        if str(event_type).strip() != str(m.group(1)):
            raise ValueError(
                f"invalid intent '{key}': payload.event_type must equal '{m.group(1)}'"
            )
        return

    if key == "inbox.read_ack":
        if str(source_kind or "").strip() != "inbox":
            raise ValueError("invalid intent 'inbox.read_ack': source_kind must be 'inbox'")
        allowed = {"event_ids", "count"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent 'inbox.read_ack': unsupported payload keys: {', '.join(unknown)}"
            )
        event_ids = _expect_field_type(data, "event_ids", list, where=key)
        if not all(isinstance(x, str) for x in event_ids):
            raise ValueError("invalid intent 'inbox.read_ack': payload.event_ids must be string array")
        _expect_field_type(data, "count", int, where=key)
        return

    if key == "inbox.received.unread" or _INBOX_NOTICE_RE.match(key):
        if str(source_kind or "").strip() != "inbox":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'inbox'")
        allowed = {"title", "sender", "message_id", "msg_type", "content", "payload", "attachments"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        _expect_field_type(data, "title", str, where=key)
        _expect_field_type(data, "sender", str, where=key)
        _expect_field_type(data, "message_id", str, where=key)
        _expect_field_type(data, "msg_type", str, where=key)
        _expect_field_type(data, "content", str, where=key)
        _expect_field_type(data, "payload", dict, where=key)
        if "attachments" in data:
            rows = _expect_field_type(data, "attachments", list, where=key)
            if not all(isinstance(x, str) for x in rows):
                raise ValueError(f"invalid intent '{key}': payload.attachments must be string array")
        return

    if _INBOX_SECTION_RE.match(key):
        if str(source_kind or "").strip() != "inbox":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'inbox'")
        allowed = {"section", "title", "rows"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        section = _expect_field_type(data, "section", str, where=key)
        _expect_field_type(data, "title", str, where=key)
        _expect_field_type(data, "rows", str, where=key)
        expect_section = key.split(".")[-1]
        if str(section).strip() != expect_section:
            raise ValueError(
                f"invalid intent '{key}': payload.section must equal '{expect_section}'"
            )
        return

    if key.startswith("outbox.sent."):
        m = _OUTBOX_SENT_RE.match(key)
        if not m:
            raise ValueError(f"invalid intent '{key}': malformed outbox status key")
        if str(source_kind or "").strip() != "inbox":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'inbox'")
        allowed = {"title", "to_agent_id", "message_id", "status", "error_message", "attachments_count"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        _expect_field_type(data, "title", str, where=key)
        _expect_field_type(data, "to_agent_id", str, where=key)
        _expect_field_type(data, "message_id", str, where=key)
        status = _expect_field_type(data, "status", str, where=key)
        _expect_field_type(data, "error_message", str, where=key)
        if "attachments_count" in data:
            _expect_field_type(data, "attachments_count", int, where=key)
        if str(status).strip().lower() != str(m.group(1)):
            raise ValueError(
                f"invalid intent '{key}': payload.status must equal '{m.group(1)}'"
            )
        return

    if key.startswith("agent."):
        if str(source_kind or "").strip() != "agent":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'agent'")
        if key == "agent.mode.freeform":
            allowed = {"project_id", "agent_id"}
            unknown = sorted(set(data.keys()) - allowed)
            if unknown:
                raise ValueError(
                    "invalid intent 'agent.mode.freeform': unsupported payload keys: "
                    + ", ".join(unknown)
                )
            return
        if key == "agent.safety.tool_loop_cap":
            allowed = {"max_rounds"}
            unknown = sorted(set(data.keys()) - allowed)
            if unknown:
                raise ValueError(
                    "invalid intent 'agent.safety.tool_loop_cap': unsupported payload keys: "
                    + ", ".join(unknown)
                )
            _expect_field_type(data, "max_rounds", int, where=key)
            return
        if key == "agent.event.injected":
            allowed = {"count"}
            unknown = sorted(set(data.keys()) - allowed)
            if unknown:
                raise ValueError(
                    "invalid intent 'agent.event.injected': unsupported payload keys: "
                    + ", ".join(unknown)
                )
            _expect_field_type(data, "count", int, where=key)
            return
        # Keep non-core agent intents permissive for incremental migration.
        return

    if key.startswith("phase.retry."):
        m = _PHASE_RETRY_RE.match(key)
        if not m:
            raise ValueError(f"invalid intent '{key}': malformed phase retry key")
        if str(source_kind or "").strip() != "phase":
            raise ValueError(f"invalid intent '{key}': source_kind must be 'phase'")
        allowed = {"phase", "message"}
        unknown = sorted(set(data.keys()) - allowed)
        if unknown:
            raise ValueError(
                f"invalid intent '{key}': unsupported payload keys: {', '.join(unknown)}"
            )
        phase = _expect_field_type(data, "phase", str, where=key)
        _expect_field_type(data, "message", str, where=key)
        if str(phase).strip().lower() != str(m.group(1)):
            raise ValueError(
                f"invalid intent '{key}': payload.phase must equal '{m.group(1)}'"
            )
        return


def template_vars_for_intent(project_id: str, intent_key: str) -> dict[str, Any]:
    base = schema_for_intent(intent_key)
    obs = observed_schema(project_id).get(intent_key, {})
    fields = obs.get("fields") if isinstance(obs, dict) else {}
    observed_vars = sorted(str(k) for k in (fields.keys() if isinstance(fields, dict) else []))
    guaranteed = sorted(set(BASE_VARS + list(base.get("guaranteed", []))))
    optional = sorted(set(list(base.get("optional", []))))
    return {
        "intent_key": str(intent_key or "").strip(),
        "guaranteed_vars": guaranteed,
        "optional_vars": optional,
        "observed_vars": observed_vars,
    }
