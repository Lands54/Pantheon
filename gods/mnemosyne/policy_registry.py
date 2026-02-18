"""Memory policy registry and strict validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gods.mnemosyne.intent_registry import tool_intent_names, registered_intent_keys, is_registered_intent_key
from gods.mnemosyne.template_registry import ensure_memory_templates, list_memory_templates
from gods.paths import mnemosyne_dir


class MemoryPolicyMissingError(RuntimeError):
    """Raised when an intent key has no strict policy entry."""


class MemoryTemplateMissingError(RuntimeError):
    """Raised when a configured template cannot be resolved."""


_RULE_KEYS = {
    "to_chronicle",
    "to_runtime_log",
    "to_llm_context",
    "chronicle_template_key",
    "runtime_log_template_key",
    "llm_context_template_key",
}

_LEGACY_INTENT_KEY_MAP: dict[str, str] = {
    "inbox.summary": "inbox.section.summary",
    "inbox.section.mailbox": "inbox.section.summary",
    "tool.read_file.ok": "tool.read.ok",
    "tool.read_file.error": "tool.read.error",
    "tool.read_file.blocked": "tool.read.blocked",
    "tool.list_dir.ok": "tool.list.ok",
    "tool.list_dir.error": "tool.list.error",
    "tool.list_dir.blocked": "tool.list.blocked",
}


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def policy_path(project_id: str) -> Path:
    return _mn_root(project_id) / "memory_policy.json"


def required_intent_keys() -> list[str]:
    return registered_intent_keys()


def default_memory_policy() -> dict[str, dict[str, Any]]:
    def _rule(
        to_chronicle: bool,
        to_runtime_log: bool,
        to_llm_context: bool = False,
        chronicle_key: str = "",
        runtime_key: str = "",
        llm_context_key: str = "",
    ) -> dict[str, Any]:
        return {
            "to_chronicle": bool(to_chronicle),
            "to_runtime_log": bool(to_runtime_log),
            "to_llm_context": bool(to_llm_context),
            "chronicle_template_key": str(chronicle_key or ""),
            "runtime_log_template_key": str(runtime_key or ""),
            "llm_context_template_key": str(llm_context_key or ""),
        }

    policy: dict[str, dict[str, Any]] = {
        "event.mail_event": _rule(False, True),
        "event.timer": _rule(False, True),
        "event.manual": _rule(False, True),
        "event.system": _rule(False, True),
        "event.interaction.message.sent": _rule(False, True),
        "event.interaction.message.read": _rule(False, True),
        "event.interaction.hermes.notice": _rule(False, True),
        "event.interaction.detach.notice": _rule(False, True),
        "event.interaction.agent.trigger": _rule(False, True),
        "event.hermes_protocol_invoked_event": _rule(False, True),
        "event.hermes_job_updated_event": _rule(False, True),
        "event.hermes_contract_registered_event": _rule(False, True),
        "event.hermes_contract_committed_event": _rule(False, True),
        "event.hermes_contract_disabled_event": _rule(False, True),
        "event.detach_submitted_event": _rule(False, True),
        "event.detach_started_event": _rule(False, True),
        "event.detach_stopping_event": _rule(False, True),
        "event.detach_stopped_event": _rule(False, True),
        "event.detach_failed_event": _rule(False, True),
        "event.detach_reconciled_event": _rule(False, True),
        "event.detach_lost_event": _rule(False, True),
        "inbox.received.unread": _rule(False, True),
        "inbox.notice.contract_commit_notice": _rule(True, True, True, "memory_inbox_notice_contract_commit", "", "memory_inbox_notice_contract_commit"),
        "inbox.notice.contract_fully_committed": _rule(True, True, True, "memory_inbox_notice_contract_fully_committed", "", "memory_inbox_notice_contract_fully_committed"),
        "inbox.read_ack": _rule(False, True),
        "outbox.sent.pending": _rule(False, True),
        "outbox.sent.delivered": _rule(False, True),
        "outbox.sent.handled": _rule(False, True),
        "outbox.sent.failed": _rule(False, True),
        "inbox.section.summary": _rule(False, False, True, "", "", "memory_inbox_section_summary"),
        "inbox.section.recent_read": _rule(False, False, True, "", "", "memory_inbox_section_recent_read"),
        "inbox.section.recent_send": _rule(False, False, True, "", "", "memory_inbox_section_recent_send"),
        "inbox.section.inbox_unread": _rule(False, False, True, "", "", "memory_inbox_section_inbox_unread"),
        "llm.response": _rule(True, False, False, "memory_llm_response", ""),
        "agent.mode.freeform": _rule(False, True),
        "agent.safety.tool_loop_cap": _rule(False, True),
        "agent.event.injected": _rule(False, True),
        "phase.retry.reason": _rule(False, True),
        "phase.retry.act": _rule(False, True),
        "phase.retry.observe": _rule(False, True),
    }
    for tool_name in tool_intent_names():
        policy[f"tool.{tool_name}.ok"] = _rule(True, False, False, "memory_tool_ok", "")
        policy[f"tool.{tool_name}.error"] = _rule(True, True, True, "memory_tool_error", "")
        policy[f"tool.{tool_name}.blocked"] = _rule(False, True, True, "", "")
    return policy


def default_intent_rule(intent_key: str) -> dict[str, Any]:
    key = str(intent_key or "").strip()
    if key == "inbox.section.summary":
        return {
            "to_chronicle": False,
            "to_runtime_log": False,
            "to_llm_context": True,
            "chronicle_template_key": "",
            "runtime_log_template_key": "",
            "llm_context_template_key": "memory_inbox_section_summary",
        }
    if key == "inbox.section.recent_read":
        return {
            "to_chronicle": False,
            "to_runtime_log": False,
            "to_llm_context": True,
            "chronicle_template_key": "",
            "runtime_log_template_key": "",
            "llm_context_template_key": "memory_inbox_section_recent_read",
        }
    if key == "inbox.section.recent_send":
        return {
            "to_chronicle": False,
            "to_runtime_log": False,
            "to_llm_context": True,
            "chronicle_template_key": "",
            "runtime_log_template_key": "",
            "llm_context_template_key": "memory_inbox_section_recent_send",
        }
    if key == "inbox.section.inbox_unread":
        return {
            "to_chronicle": False,
            "to_runtime_log": False,
            "to_llm_context": True,
            "chronicle_template_key": "",
            "runtime_log_template_key": "",
            "llm_context_template_key": "memory_inbox_section_inbox_unread",
        }
    return {
        "to_chronicle": False,
        "to_runtime_log": True,
        "to_llm_context": False,
        "chronicle_template_key": "",
        "runtime_log_template_key": "",
        "llm_context_template_key": "",
    }


def _load_raw_policy(path: Path, *, project_id: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise MemoryPolicyMissingError(f"invalid memory policy json for project={project_id}: {e}") from e
    if not isinstance(raw, dict):
        raise MemoryPolicyMissingError(f"memory policy must be an object: project={project_id}")
    return raw


def _normalize_rule(rule: dict[str, Any], *, intent_key: str, project_id: str) -> dict[str, Any]:
    unknown_fields = sorted(set(rule.keys()) - _RULE_KEYS)
    if unknown_fields:
        raise MemoryPolicyMissingError(
            f"memory policy has unsupported fields for '{intent_key}' in project={project_id}: "
            f"{', '.join(unknown_fields)}"
        )
    return {
        "to_chronicle": bool(rule.get("to_chronicle", False)),
        "to_runtime_log": bool(rule.get("to_runtime_log", False)),
        "to_llm_context": bool(rule.get("to_llm_context", False)),
        "chronicle_template_key": str(rule.get("chronicle_template_key", "") or "").strip(),
        "runtime_log_template_key": str(rule.get("runtime_log_template_key", "") or "").strip(),
        "llm_context_template_key": str(rule.get("llm_context_template_key", "") or "").strip(),
    }


def ensure_memory_policy(project_id: str) -> Path:
    ensure_memory_templates(project_id)
    path = policy_path(project_id)
    default_payload = default_memory_policy()
    if not path.exists():
        path.write_text(json.dumps(default_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    raw = _load_raw_policy(path, project_id=project_id)
    changed = False
    # Zero-compat migration: rewrite known legacy intent keys to canonical keys.
    # Unknown keys are still rejected later by validate_memory_policy.
    for legacy, canonical in _LEGACY_INTENT_KEY_MAP.items():
        if legacy not in raw:
            continue
        legacy_rule = raw.get(legacy)
        if canonical not in raw and isinstance(legacy_rule, dict):
            raw[canonical] = _normalize_rule(legacy_rule, intent_key=legacy, project_id=project_id)
        del raw[legacy]
        changed = True
    for k, v in default_payload.items():
        if k not in raw:
            raw[k] = v
            changed = True
        elif not isinstance(raw.get(k), dict):
            raise MemoryPolicyMissingError(f"memory policy key must be object for '{k}' in project={project_id}")
        else:
            normalized = _normalize_rule(raw[k], intent_key=k, project_id=project_id)
            if normalized != raw[k]:
                raw[k] = normalized
                changed = True
    if changed:
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ensure_intent_policy_rule(project_id: str, intent_key: str) -> dict[str, Any]:
    key = str(intent_key or "").strip()
    if not key:
        raise MemoryPolicyMissingError("intent_key is required")
    if not is_registered_intent_key(key):
        raise MemoryPolicyMissingError(
            f"unregistered intent_key='{key}' in project={project_id}; register in required_intent_keys first"
        )
    path = ensure_memory_policy(project_id)
    raw = _load_raw_policy(path, project_id=project_id)
    rule = raw.get(key)
    if rule is None:
        raise MemoryPolicyMissingError(
            f"memory policy missing registered key '{key}' in project={project_id}"
        )
    if not isinstance(rule, dict):
        raise MemoryPolicyMissingError(f"memory policy key must be object for '{key}' in project={project_id}")
    return _normalize_rule(rule, intent_key=key, project_id=project_id)


def load_memory_policy(project_id: str, *, ensure_exists: bool = True) -> dict[str, dict[str, Any]]:
    if ensure_exists:
        ensure_memory_policy(project_id)
    path = policy_path(project_id)
    if not path.exists():
        return {}
    raw = _load_raw_policy(path, project_id=project_id)
    out: dict[str, dict[str, Any]] = {}
    for key, rule in raw.items():
        if not isinstance(rule, dict):
            continue
        out[str(key)] = _normalize_rule(rule, intent_key=str(key), project_id=project_id)
    return out


def validate_memory_policy(project_id: str, *, ensure_exists: bool = True) -> dict[str, Any]:
    policy = load_memory_policy(project_id, ensure_exists=ensure_exists)
    required = required_intent_keys()
    missing = [k for k in required if k not in policy]
    if missing:
        raise MemoryPolicyMissingError(
            f"memory policy missing {len(missing)} key(s) in project={project_id}: {', '.join(missing[:20])}"
        )
    unknown = [k for k in policy.keys() if k not in set(required)]
    if unknown:
        raise MemoryPolicyMissingError(
            f"memory policy has unregistered key(s) in project={project_id}: {', '.join(sorted(unknown)[:20])}"
        )

    runtime_keys = set(list_memory_templates(project_id, "runtime_log").keys())
    chronicle_keys = set(list_memory_templates(project_id, "chronicle").keys())
    missing_templates: list[str] = []
    chronicle_template_required_missing: list[str] = []
    for key in required:
        rule = policy.get(key, {}) or {}
        chronicle_tpl = str(rule.get("chronicle_template_key", "")).strip()
        runtime_tpl = str(rule.get("runtime_log_template_key", "")).strip()
        if bool(rule.get("to_chronicle", False)) and not chronicle_tpl:
            chronicle_template_required_missing.append(key)
        if chronicle_tpl and chronicle_tpl not in chronicle_keys:
            missing_templates.append(f"{key}:chronicle:{chronicle_tpl}")
        if runtime_tpl and runtime_tpl not in runtime_keys:
            missing_templates.append(f"{key}:runtime_log:{runtime_tpl}")

    if chronicle_template_required_missing:
        raise MemoryTemplateMissingError(
            f"memory policy requires chronicle template for {len(chronicle_template_required_missing)} key(s) "
            f"in project={project_id}: {', '.join(chronicle_template_required_missing[:20])}"
        )
    if missing_templates:
        raise MemoryTemplateMissingError(
            f"memory policy template missing {len(missing_templates)} key(s) in project={project_id}: "
            + ", ".join(missing_templates[:20])
        )

    return {
        "project_id": project_id,
        "required_keys": len(required),
        "validated_keys": len(required),
        "missing_keys": [],
        "missing_templates": [],
    }


def list_policy_rules(project_id: str) -> dict[str, dict[str, Any]]:
    return load_memory_policy(project_id, ensure_exists=True)


def upsert_policy_rule(
    project_id: str,
    intent_key: str,
    *,
    to_chronicle: bool | None = None,
    to_runtime_log: bool | None = None,
    to_llm_context: bool | None = None,
    chronicle_template_key: str | None = None,
    runtime_log_template_key: str | None = None,
    llm_context_template_key: str | None = None,
) -> dict[str, Any]:
    key = str(intent_key or "").strip()
    if not key:
        raise MemoryPolicyMissingError("intent_key is required")
    if not is_registered_intent_key(key):
        raise MemoryPolicyMissingError(
            f"unregistered intent_key='{key}' in project={project_id}; register in required_intent_keys first"
        )
    path = ensure_memory_policy(project_id)
    raw = _load_raw_policy(path, project_id=project_id)
    current = raw.get(key)
    if current is None:
        raise MemoryPolicyMissingError(
            f"memory policy missing registered key '{key}' in project={project_id}"
        )
    if not isinstance(current, dict):
        raise MemoryPolicyMissingError(f"memory policy key must be object for '{key}' in project={project_id}")
    normalized = _normalize_rule(current, intent_key=key, project_id=project_id)
    if to_chronicle is not None:
        normalized["to_chronicle"] = bool(to_chronicle)
    if to_runtime_log is not None:
        normalized["to_runtime_log"] = bool(to_runtime_log)
    if to_llm_context is not None:
        normalized["to_llm_context"] = bool(to_llm_context)
    if chronicle_template_key is not None:
        normalized["chronicle_template_key"] = str(chronicle_template_key or "").strip()
    if runtime_log_template_key is not None:
        normalized["runtime_log_template_key"] = str(runtime_log_template_key or "").strip()
    if llm_context_template_key is not None:
        normalized["llm_context_template_key"] = str(llm_context_template_key or "").strip()
    raw[key] = normalized
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized
