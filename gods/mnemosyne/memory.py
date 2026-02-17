"""Mnemosyne typed memory sinks."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

from gods.mnemosyne.contracts import MemoryDecision, MemoryIntent, MemorySinkPolicy
from gods.mnemosyne.policy_registry import (
    MemoryPolicyMissingError,
    MemoryTemplateMissingError,
    ensure_memory_policy,
    load_memory_policy as _load_strict_policy,
)
from gods.paths import mnemosyne_dir
from gods.prompts import prompt_registry
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
        raise MemoryPolicyMissingError(
            f"no memory policy for intent_key='{key}' in project={intent.project_id}"
        )
    return MemorySinkPolicy(
        to_chronicle=bool(rule.get("to_chronicle", False)),
        to_runtime_log=bool(rule.get("to_runtime_log", False)),
        template=str(rule.get("template", "") or "").strip(),
    )


def _render_text(intent: MemoryIntent, sink: MemorySinkPolicy) -> str:
    if not sink.template:
        return str(intent.fallback_text or "")
    try:
        raw = prompt_registry.get(sink.template, project_id=intent.project_id)
    except Exception as e:
        raise MemoryTemplateMissingError(
            f"template '{sink.template}' not found for intent_key='{intent.intent_key}' "
            f"(project={intent.project_id})"
        ) from e
    render_vars = dict(intent.payload or {})
    render_vars.setdefault("project_id", intent.project_id)
    render_vars.setdefault("agent_id", intent.agent_id)
    render_vars.setdefault("intent_key", intent.intent_key)
    return Template(raw).safe_substitute(**render_vars)


def record_intent(intent: MemoryIntent) -> dict[str, Any]:
    sink = _resolve_policy(intent)
    text = _render_text(intent, sink)

    chronicle_written = False
    if sink.to_chronicle and str(text or "").strip():
        _append_chronicle(intent.project_id, intent.agent_id, text)
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
                "text": text,
                "payload": intent.payload or {},
                "rule": {
                    "to_chronicle": sink.to_chronicle,
                    "to_runtime_log": sink.to_runtime_log,
                    "template": sink.template,
                },
            },
        )
        runtime_written = True

    decision = MemoryDecision(
        intent_key=intent.intent_key,
        chronicle_written=chronicle_written,
        runtime_log_written=runtime_written,
        text=text,
        policy=sink,
    )
    return {
        "intent_key": decision.intent_key,
        "chronicle_written": decision.chronicle_written,
        "runtime_log_written": decision.runtime_log_written,
        "text": decision.text,
        "rule": {
            "to_chronicle": decision.policy.to_chronicle,
            "to_runtime_log": decision.policy.to_runtime_log,
            "template": decision.policy.template,
        },
    }
