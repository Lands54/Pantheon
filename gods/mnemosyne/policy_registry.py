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
    "tool.run_command_detach.ok": "tool.run_command.ok",
    "tool.run_command_detach.error": "tool.run_command.error",
    "tool.run_command_detach.blocked": "tool.run_command.blocked",
}


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def policy_path(project_id: str) -> Path:
    return _mn_root(project_id) / "memory_policy.json"


def required_intent_keys() -> list[str]:
    return registered_intent_keys()


from gods.mnemosyne.semantics import semantics_service


def default_memory_policy() -> dict[str, dict[str, Any]]:
    policy: dict[str, dict[str, Any]] = {}
    for key in semantics_service.list_intent_keys():
        p = semantics_service.get_policy(key)
        if p:
            policy[key] = {
                "to_chronicle": p.get("to_chronicle", False),
                "to_runtime_log": p.get("to_runtime_log", False),
                "to_llm_context": p.get("to_llm_context", False),
                "chronicle_template_key": p.get("chronicle_template_key", ""),
                "runtime_log_template_key": p.get("runtime_log_template_key", ""),
                "llm_context_template_key": p.get("llm_context_template_key", ""),
            }
        else:
            # Fallback for keys without explicit policy
            policy[key] = {
                "to_chronicle": False,
                "to_runtime_log": True,
                "to_llm_context": False,
                "chronicle_template_key": "",
                "runtime_log_template_key": "",
                "llm_context_template_key": "",
            }
    return policy


def default_intent_rule(intent_key: str) -> dict[str, Any]:
    p = semantics_service.get_policy(intent_key)
    if p:
        return {
            "to_chronicle": p.get("to_chronicle", False),
            "to_runtime_log": p.get("to_runtime_log", False),
            "to_llm_context": p.get("to_llm_context", False),
            "chronicle_template_key": p.get("chronicle_template_key", ""),
            "runtime_log_template_key": p.get("runtime_log_template_key", ""),
            "llm_context_template_key": p.get("llm_context_template_key", ""),
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
    from gods.mnemosyne.template_registry import ensure_memory_templates
    ensure_memory_templates(project_id)
    path = policy_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    default_payload = default_memory_policy()
    
    if not path.exists():
        path.write_text(json.dumps(default_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    raw = _load_raw_policy(path, project_id=project_id)
    changed = False
    
    # Migrate known legacy keys first.
    for legacy_key, new_key in _LEGACY_INTENT_KEY_MAP.items():
        if legacy_key not in raw:
            continue
        if new_key in default_payload and new_key not in raw and isinstance(raw.get(legacy_key), dict):
            raw[new_key] = _normalize_rule(raw[legacy_key], intent_key=legacy_key, project_id=project_id)
        raw.pop(legacy_key, None)
        changed = True

    # Weak-mode: keep unknown keys and only add/normalize registered defaults.
    required_keys = set(default_payload.keys())

    for k in required_keys:
        if k not in raw:
            raw[k] = default_payload[k]
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
    path = ensure_memory_policy(project_id)
    raw = _load_raw_policy(path, project_id=project_id)
    rule = raw.get(key)
    if rule is None:
        # Weak-mode: allow dynamic intent keys and auto-seed default rule.
        rule = default_intent_rule(key)
        raw[key] = rule
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
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
    # Weak-mode: unknown keys are tolerated; missing registered keys are
    # auto-filled from defaults for forward progress.
    unknown = [k for k in policy.keys() if k not in set(required)]
    if missing:
        path = policy_path(project_id)
        raw = _load_raw_policy(path, project_id=project_id)
        changed = False
        for k in missing:
            if k in raw and isinstance(raw.get(k), dict):
                continue
            raw[k] = default_intent_rule(k)
            changed = True
        if changed:
            path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        policy = load_memory_policy(project_id, ensure_exists=False)
        missing = [k for k in required if k not in policy]

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

    # Weak-mode: template presence is no longer a hard requirement.

    return {
        "project_id": project_id,
        "required_keys": len(required),
        "validated_keys": len(policy),
        "missing_keys": missing,
        "unknown_keys": unknown,
        "missing_templates": missing_templates,
        "missing_chronicle_templates": chronicle_template_required_missing,
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
    path = ensure_memory_policy(project_id)
    raw = _load_raw_policy(path, project_id=project_id)
    current = raw.get(key)
    if current is None:
        current = default_intent_rule(key)
        raw[key] = current
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
