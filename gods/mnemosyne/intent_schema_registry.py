"""Intent payload schema registry and observed-variable collector."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.paths import mnemosyne_dir

BASE_VARS = ["project_id", "agent_id", "intent_key"]

_EXPLICIT: dict[str, dict[str, Any]] = {
    "llm.response": {"guaranteed": ["phase", "content"], "optional": []},
    "inbox.read_ack": {"guaranteed": ["event_ids", "count"], "optional": []},
    "inbox.received.unread": {"guaranteed": ["title", "sender", "message_id", "msg_type"], "optional": []},
    "outbox.sent.pending": {"guaranteed": ["title", "to_agent_id", "message_id", "status", "error_message"], "optional": []},
    "outbox.sent.delivered": {"guaranteed": ["title", "to_agent_id", "message_id", "status", "error_message"], "optional": []},
    "outbox.sent.handled": {"guaranteed": ["title", "to_agent_id", "message_id", "status", "error_message"], "optional": []},
    "outbox.sent.failed": {"guaranteed": ["title", "to_agent_id", "message_id", "status", "error_message"], "optional": []},
    "agent.mode.freeform": {"guaranteed": [], "optional": []},
    "agent.safety.tool_loop_cap": {"guaranteed": ["max_rounds"], "optional": []},
    "agent.event.injected": {"guaranteed": ["count"], "optional": []},
    "phase.retry.reason": {"guaranteed": ["phase", "message"], "optional": []},
    "phase.retry.act": {"guaranteed": ["phase", "message"], "optional": []},
    "phase.retry.observe": {"guaranteed": ["phase", "message"], "optional": []},
}


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
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
        cur["last_seen_value"] = str(v)[:120]
        fields[fk] = cur
    row["fields"] = fields
    raw[key] = row
    _write_observed(path, raw)


def schema_for_intent(intent_key: str) -> dict[str, list[str]]:
    k = str(intent_key or "").strip()
    if k in _EXPLICIT:
        row = _EXPLICIT[k]
        return {"guaranteed": list(row.get("guaranteed", [])), "optional": list(row.get("optional", []))}
    if k.startswith("tool."):
        return {"guaranteed": ["tool_name", "status", "args", "result", "result_compact"], "optional": []}
    if k.startswith("event."):
        return {"guaranteed": ["stage", "event_id", "event_type", "priority", "attempt", "max_attempts", "payload"], "optional": []}
    return {"guaranteed": [], "optional": []}


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
