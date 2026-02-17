"""Mnemosyne typed memory sinks."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from gods.mnemosyne.contracts import MemoryDecision, MemoryIntent, MemorySinkPolicy
from gods.mnemosyne.policy_registry import (
    MemoryPolicyMissingError,
    MemoryTemplateMissingError,
    ensure_intent_policy_rule,
    ensure_memory_policy,
    load_memory_policy as _load_strict_policy,
)
from gods.mnemosyne.intent_schema_registry import observe_intent_payload
from gods.mnemosyne.template_registry import render_memory_template
from gods.paths import mnemosyne_dir
from gods.mnemosyne.compaction import ensure_compacted


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _policy_path(project_id: str) -> Path:
    return _mn_root(project_id) / "memory_policy.json"


def _runtime_events_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "runtime_events" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _chronicle_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "chronicles" / f"{agent_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_memory_policy(project_id: str) -> dict[str, Any]:
    # Strict typed policy: no default fallback.
    ensure_memory_policy(project_id)
    return _load_strict_policy(project_id, ensure_exists=True)


def _append_chronicle(project_id: str, agent_id: str, text: str):
    path = _chronicle_path(project_id, agent_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n### 📖 Entry [{timestamp}]\n{text or ''}\n\n---\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)


def _append_runtime_event(project_id: str, agent_id: str, row: dict[str, Any]):
    path = _runtime_events_path(project_id, agent_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _resolve_policy(intent: MemoryIntent) -> MemorySinkPolicy:
    policy = load_memory_policy(intent.project_id)
    key = str(intent.intent_key or "").strip()
    rule = policy.get(key)
    if not isinstance(rule, dict):
        rule = ensure_intent_policy_rule(intent.project_id, key)
        policy = load_memory_policy(intent.project_id)
        rule = policy.get(key)
    if not isinstance(rule, dict):
        raise MemoryPolicyMissingError(f"no memory policy for intent_key='{key}' in project={intent.project_id}")
    tpl_chronicle = str(rule.get("chronicle_template_key", "") or "").strip()
    tpl_runtime = str(rule.get("runtime_log_template_key", "") or "").strip()
    tpl_llm = str(rule.get("llm_context_template_key", "") or "").strip()
    sink = MemorySinkPolicy(
        to_chronicle=bool(rule.get("to_chronicle", False)),
        to_runtime_log=bool(rule.get("to_runtime_log", False)),
        to_llm_context=bool(rule.get("to_llm_context", False)),
        chronicle_template_key=tpl_chronicle,
        runtime_log_template_key=tpl_runtime,
        llm_context_template_key=tpl_llm,
    )
    if sink.to_chronicle and not sink.chronicle_template_key:
        raise MemoryTemplateMissingError(
            f"to_chronicle=true requires chronicle_template_key for intent_key='{key}' (project={intent.project_id})"
        )
    return sink


def _render_template(intent: MemoryIntent, scope: str, template_key: str) -> str:
    if not template_key:
        return str(intent.fallback_text or "")
    render_vars = dict(intent.payload or {})
    render_vars.setdefault("project_id", intent.project_id)
    render_vars.setdefault("agent_id", intent.agent_id)
    render_vars.setdefault("intent_key", intent.intent_key)
    try:
        return render_memory_template(intent.project_id, scope, template_key, render_vars)
    except Exception as e:
        raise MemoryTemplateMissingError(
            f"template '{template_key}' not found for intent_key='{intent.intent_key}' "
            f"(project={intent.project_id})"
        ) from e


def _render_runtime_fallback(intent: MemoryIntent) -> str:
    summary = str(intent.fallback_text or f"[{intent.source_kind}] {intent.intent_key}").strip()
    payload = intent.payload or {}
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        payload_json = "{}"
    text = f"{summary}\n\npayload={payload_json}".strip()
    return text[:12000]


def record_intent(intent: MemoryIntent) -> dict[str, Any]:
    observe_intent_payload(intent.project_id, intent.intent_key, intent.payload or {})
    sink = _resolve_policy(intent)
    chronicle_text = ""
    runtime_text = ""
    if sink.to_chronicle:
        chronicle_text = _render_template(intent, "chronicle", sink.chronicle_template_key)
    if sink.to_runtime_log:
        if sink.runtime_log_template_key:
            runtime_text = _render_template(intent, "runtime_log", sink.runtime_log_template_key)
        else:
            runtime_text = _render_runtime_fallback(intent)

    llm_context_rendered: str | None = None
    if sink.to_llm_context:
        # Default to fallback if no specific template is set but enabled.
        if sink.llm_context_template_key:
            llm_context_rendered = _render_template(intent, "llm_context", sink.llm_context_template_key)
        else:
            # For context, we often prefer a short fallback if template missing.
            llm_context_rendered = str(intent.fallback_text or "")

    chronicle_written = False
    if sink.to_chronicle and str(chronicle_text or "").strip():
        _append_chronicle(intent.project_id, intent.agent_id, chronicle_text)
        try:
            ensure_compacted(intent.project_id, intent.agent_id)
        except Exception:
            pass
        chronicle_written = True

    runtime_written = False
    if sink.to_runtime_log:
        _append_runtime_event(
            intent.project_id,
            intent.agent_id,
            {
                "timestamp": float(intent.timestamp or time.time()),
                "project_id": intent.project_id,
                "agent_id": intent.agent_id,
                "intent_key": intent.intent_key,
                "source_kind": intent.source_kind,
                "text": runtime_text,
                "payload": intent.payload or {},
                "rule": {
                    "to_chronicle": sink.to_chronicle,
                    "to_runtime_log": sink.to_runtime_log,
                    "chronicle_template_key": sink.chronicle_template_key,
                    "runtime_log_template_key": sink.runtime_log_template_key,
                },
            },
        )
        runtime_written = True

    decision = MemoryDecision(
        intent_key=intent.intent_key,
        chronicle_written=chronicle_written,
        runtime_log_written=runtime_written,
        text=chronicle_text or runtime_text,
        policy=sink,
        llm_context_rendered=llm_context_rendered,
    )
    return {
        "intent_key": decision.intent_key,
        "chronicle_written": decision.chronicle_written,
        "runtime_log_written": decision.runtime_log_written,
        "text": decision.text,
        "chronicle_text": chronicle_text,
        "runtime_text": runtime_text,
        "rule": {
            "to_chronicle": decision.policy.to_chronicle,
            "to_runtime_log": decision.policy.to_runtime_log,
            "chronicle_template_key": decision.policy.chronicle_template_key,
            "runtime_log_template_key": decision.policy.runtime_log_template_key,
            "llm_context_template_key": decision.policy.llm_context_template_key,
        },
        "llm_context_rendered": decision.llm_context_rendered,
    }

def render_intent_for_llm_context(intent: MemoryIntent) -> str | None:
    """
    Renders an intent for LLM context purely based on policy, without persisting.
    """
    try:
        sink = _resolve_policy(intent)
        if not sink.to_llm_context:
            return None
        if sink.llm_context_template_key:
            return _render_template(intent, "llm_context", sink.llm_context_template_key)
        return str(intent.fallback_text or "")
    except Exception:
        return None
