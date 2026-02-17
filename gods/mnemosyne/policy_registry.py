"""Memory policy registry and strict validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gods.mnemosyne.intent_registry import tool_intent_names
from gods.paths import mnemosyne_dir
from gods.prompts import prompt_registry


class MemoryPolicyMissingError(RuntimeError):
    """Raised when an intent key has no strict policy entry."""


class MemoryTemplateMissingError(RuntimeError):
    """Raised when a configured template cannot be resolved."""


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def policy_path(project_id: str) -> Path:
    return _mn_root(project_id) / "memory_policy.json"


def required_intent_keys() -> list[str]:
    keys = [
        "event.mail_event",
        "event.timer",
        "event.manual",
        "event.system",
        "inbox.received.unread",
        "inbox.read_ack",
        "outbox.sent.pending",
        "outbox.sent.delivered",
        "outbox.sent.handled",
        "outbox.sent.failed",
        "llm.response",
        "agent.mode.freeform",
        "agent.safety.tool_loop_cap",
        "agent.event.injected",
        "phase.retry.reason",
        "phase.retry.act",
        "phase.retry.observe",
    ]
    for tool_name in tool_intent_names():
        keys.append(f"tool.{tool_name}.ok")
        keys.append(f"tool.{tool_name}.error")
        keys.append(f"tool.{tool_name}.blocked")
    return sorted(set(keys))


def default_memory_policy() -> dict[str, dict[str, Any]]:
    policy: dict[str, dict[str, Any]] = {
        "event.mail_event": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_event_mail_event"},
        "event.timer": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_event_timer"},
        "event.manual": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_event_manual"},
        "event.system": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_event_system"},
        "inbox.received.unread": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_inbox_received_unread"},
        "inbox.notice.contract_commit_notice": {
            "to_chronicle": True,
            "to_runtime_log": True,
            "template": "memory_inbox_notice_contract_commit",
        },
        "inbox.notice.contract_fully_committed": {
            "to_chronicle": True,
            "to_runtime_log": True,
            "template": "memory_inbox_notice_contract_fully_committed",
        },
        "inbox.read_ack": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_inbox_read_ack"},
        "outbox.sent.pending": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_outbox_pending"},
        "outbox.sent.delivered": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_outbox_delivered"},
        "outbox.sent.handled": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_outbox_handled"},
        "outbox.sent.failed": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_outbox_failed"},
        "llm.response": {"to_chronicle": True, "to_runtime_log": False, "template": "memory_llm_response"},
        "agent.mode.freeform": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_agent_mode_freeform"},
        "agent.safety.tool_loop_cap": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_agent_safety_tool_loop_cap"},
        "agent.event.injected": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_agent_event_injected"},
        "phase.retry.reason": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_phase_retry_reason"},
        "phase.retry.act": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_phase_retry_act"},
        "phase.retry.observe": {"to_chronicle": False, "to_runtime_log": True, "template": "memory_phase_retry_observe"},
    }
    for tool_name in tool_intent_names():
        policy[f"tool.{tool_name}.ok"] = {"to_chronicle": True, "to_runtime_log": False, "template": "memory_tool_ok"}
        policy[f"tool.{tool_name}.error"] = {"to_chronicle": True, "to_runtime_log": True, "template": "memory_tool_error"}
        policy[f"tool.{tool_name}.blocked"] = {"to_chronicle": False, "to_runtime_log": True, "template": "memory_tool_blocked"}
    return policy


def ensure_memory_policy(project_id: str) -> Path:
    path = policy_path(project_id)
    if path.exists():
        return path
    payload = default_memory_policy()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_memory_policy(project_id: str, *, ensure_exists: bool = True) -> dict[str, dict[str, Any]]:
    if ensure_exists:
        ensure_memory_policy(project_id)
    path = policy_path(project_id)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise MemoryPolicyMissingError(f"invalid memory policy json for project={project_id}: {e}") from e
    if not isinstance(raw, dict):
        raise MemoryPolicyMissingError(f"memory policy must be an object: project={project_id}")
    out: dict[str, dict[str, Any]] = {}
    for key, rule in raw.items():
        if not isinstance(rule, dict):
            continue
        out[str(key)] = {
            "to_chronicle": bool(rule.get("to_chronicle", False)),
            "to_runtime_log": bool(rule.get("to_runtime_log", False)),
            "template": str(rule.get("template", "") or "").strip(),
        }
    return out


def validate_memory_policy(project_id: str, *, ensure_exists: bool = True) -> dict[str, Any]:
    policy = load_memory_policy(project_id, ensure_exists=ensure_exists)
    required = required_intent_keys()
    missing = [k for k in required if k not in policy]
    if missing:
        raise MemoryPolicyMissingError(
            f"memory policy missing {len(missing)} key(s) in project={project_id}: {', '.join(missing[:20])}"
        )

    missing_templates: list[str] = []
    for key in required:
        tpl = str(policy.get(key, {}).get("template", "")).strip()
        if not tpl:
            continue
        try:
            prompt_registry.get(tpl, project_id=project_id)
        except Exception:
            missing_templates.append(f"{key}:{tpl}")
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
