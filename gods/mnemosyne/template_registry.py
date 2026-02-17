"""Project-local memory template registry."""
from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template
from typing import Any, Literal

from gods.paths import mnemosyne_dir

TemplateScope = Literal["runtime_log", "chronicle"]

_KEY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{1,127}$")
_MAX_TEMPLATE_LENGTH = 12000

_DEFAULT_RUNTIME_LOG_TEMPLATES: dict[str, str] = {
    "memory_event_mail_event": "[EVENT] mail_event stage=$stage event_id=$event_id reason=$event_type",
    "memory_event_timer": "[EVENT] timer stage=$stage reason=$event_type",
    "memory_event_manual": "[EVENT] manual stage=$stage reason=$event_type",
    "memory_event_system": "[EVENT] system stage=$stage reason=$event_type",
    "memory_inbox_read_ack": "[INBOX_READ_ACK] count=$count ids=$event_ids",
    "memory_inbox_received_unread": "[INBOX_UNREAD] title=$title from=$sender id=$message_id",
    "memory_outbox_pending": "[OUTBOX] [title=$title][to=$to_agent_id][status=pending] mid=$message_id",
    "memory_outbox_delivered": "[OUTBOX] [title=$title][to=$to_agent_id][status=delivered] mid=$message_id",
    "memory_outbox_handled": "[OUTBOX] [title=$title][to=$to_agent_id][status=handled] mid=$message_id",
    "memory_outbox_failed": "[OUTBOX] [title=$title][to=$to_agent_id][status=failed] mid=$message_id error=$error_message",
    "memory_agent_mode_freeform": "[MODE] freeform activated for agent=$agent_id in project=$project_id.",
    "memory_agent_event_injected": "[EVENT_INJECTED] count=$count inbox event(s) appended after action.",
    "memory_agent_safety_tool_loop_cap": "[SAFETY] tool loop cap reached for agent=$agent_id in project=$project_id. max_rounds=$max_rounds.",
    "memory_phase_retry_reason": "[PHASE_RETRY] reason -> $message",
    "memory_phase_retry_act": "[PHASE_RETRY] act -> $message",
    "memory_phase_retry_observe": "[PHASE_RETRY] observe -> $message",
    "memory_tool_ok": "[[ACTION]] $tool_name (ok) -> $result_compact",
    "memory_tool_error": "[[ACTION]] $tool_name (error) -> $result_compact",
    "memory_tool_blocked": "[[ACTION]] $tool_name (blocked) -> $result_compact",
}

_DEFAULT_CHRONICLE_TEMPLATES: dict[str, str] = {
    "memory_llm_response": "$content",
    "memory_tool_ok": "[[ACTION]] $tool_name (ok) -> $result_compact",
    "memory_tool_error": "[[ACTION]] $tool_name (error) -> $result_compact",
    "memory_inbox_notice_contract_commit": "[COMMIT_NOTICE] [title=$title][from=$sender]",
    "memory_inbox_notice_contract_fully_committed": "[COMMIT_FULLY] [title=$title][from=$sender]",
}


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def runtime_log_templates_path(project_id: str) -> Path:
    return _mn_root(project_id) / "runtime_log_templates.json"


def chronicle_templates_path(project_id: str) -> Path:
    return _mn_root(project_id) / "chronicle_templates.json"


def _scope_path(project_id: str, scope: TemplateScope) -> Path:
    if scope == "runtime_log":
        return runtime_log_templates_path(project_id)
    if scope == "chronicle":
        return chronicle_templates_path(project_id)
    raise ValueError(f"invalid template scope: {scope}")


def _scope_defaults(scope: TemplateScope) -> dict[str, str]:
    return dict(_DEFAULT_RUNTIME_LOG_TEMPLATES if scope == "runtime_log" else _DEFAULT_CHRONICLE_TEMPLATES)


def _read_json_obj(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _validate_key(key: str) -> str:
    out = str(key or "").strip()
    if not _KEY_RE.match(out):
        raise ValueError("template key must match ^[a-zA-Z][a-zA-Z0-9_.-]{1,127}$")
    return out


def _validate_body(text: str) -> str:
    body = str(text or "")
    if len(body) > _MAX_TEMPLATE_LENGTH:
        raise ValueError(f"template body too long (max={_MAX_TEMPLATE_LENGTH})")
    if "\x00" in body:
        raise ValueError("template body contains NUL byte")
    return body


def ensure_memory_templates(project_id: str) -> None:
    for scope in ("runtime_log", "chronicle"):
        path = _scope_path(project_id, scope)
        if not path.exists():
            path.write_text(json.dumps(_scope_defaults(scope), ensure_ascii=False, indent=2), encoding="utf-8")


def list_memory_templates(project_id: str, scope: TemplateScope) -> dict[str, str]:
    ensure_memory_templates(project_id)
    path = _scope_path(project_id, scope)
    raw = _read_json_obj(path)
    out: dict[str, str] = {}
    for k, v in raw.items():
        try:
            key = _validate_key(str(k))
            out[key] = _validate_body(str(v))
        except Exception:
            continue
    return out


def get_memory_template(project_id: str, scope: TemplateScope, key: str) -> str:
    templates = list_memory_templates(project_id, scope)
    k = _validate_key(key)
    if k not in templates:
        raise KeyError(k)
    return templates[k]


def upsert_memory_template(project_id: str, scope: TemplateScope, key: str, body: str) -> dict[str, Any]:
    ensure_memory_templates(project_id)
    path = _scope_path(project_id, scope)
    raw = _read_json_obj(path)
    clean: dict[str, str] = {}
    for k, v in raw.items():
        try:
            clean[_validate_key(str(k))] = _validate_body(str(v))
        except Exception:
            continue
    k = _validate_key(key)
    clean[k] = _validate_body(body)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"scope": scope, "key": k, "template": clean[k]}


def render_memory_template(project_id: str, scope: TemplateScope, key: str, render_vars: dict[str, Any]) -> str:
    text = get_memory_template(project_id, scope, key)
    vars_safe = {str(k): "" if v is None else str(v) for k, v in (render_vars or {}).items()}
    return Template(text).safe_substitute(**vars_safe)
