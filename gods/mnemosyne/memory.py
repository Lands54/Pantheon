"""Mnemosyne typed memory sinks."""
from __future__ import annotations

import json
import os
import re
import time
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Any

from gods.mnemosyne.contracts import MemoryDecision, MemoryIntent, MemorySinkPolicy
from gods.mnemosyne.policy_registry import (
    MemoryPolicyMissingError,
    ensure_intent_policy_rule,
    ensure_memory_policy,
    load_memory_policy as _load_strict_policy,
)
from gods.mnemosyne.intent_schema_registry import observe_intent_payload, validate_intent_contract
from gods.paths import mnemosyne_dir
from gods.mnemosyne.compaction import ensure_compacted
from gods.mnemosyne.context_index import append_context_index_entry
from gods.mnemosyne.chronicle_index import append_chronicle_index_entry


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


def _intents_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "intents" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _intent_seq_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "intent_seq" / f"{agent_id}.txt"
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


def _append_intent(project_id: str, agent_id: str, row: dict[str, Any]):
    path = _intents_path(project_id, agent_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _scan_max_intent_seq(project_id: str, agent_id: str) -> int:
    path = _intents_path(project_id, agent_id)
    if not path.exists():
        return 0
    max_seq = 0
    rows = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows += 1
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            seq = row.get("intent_seq")
            try:
                seq_i = int(seq)
            except Exception:
                continue
            if seq_i > max_seq:
                max_seq = seq_i
    # Legacy rows may not have intent_seq. Fallback to row count to keep uniqueness.
    return max(max_seq, rows)

def fetch_intents_between(project_id: str, agent_id: str, start_seq: int, end_seq: int) -> list[MemoryIntent]:
    path = _intents_path(project_id, agent_id)
    if not path.exists() or start_seq > end_seq:
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            try:
                seq = int(row.get("intent_seq", 0) or 0)
            except Exception:
                continue
            if start_seq <= seq <= end_seq:
                try:
                    intent = MemoryIntent(
                        intent_key=str(row.get("intent_key", "") or ""),
                        project_id=str(row.get("project_id", "") or ""),
                        agent_id=str(row.get("agent_id", "") or ""),
                        source_kind=str(row.get("source_kind", "") or ""),
                        payload=row.get("payload", {}) or {},
                        fallback_text=str(row.get("fallback_text", "") or ""),
                        timestamp=float(row.get("timestamp") or time.time()),
                    )
                    setattr(intent, "intent_seq", seq)
                    setattr(intent, "intent_id", str(row.get("intent_id", "") or ""))
                    out.append(intent)
                except Exception:
                    continue
            if seq > end_seq:
                break
    return out



def _next_intent_seq(project_id: str, agent_id: str) -> int:
    path = _intent_seq_path(project_id, agent_id)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = str(f.read() or "").strip()
            try:
                current = int(raw)
            except Exception:
                current = 0
            if current <= 0:
                current = _scan_max_intent_seq(project_id, agent_id)
            nxt = max(1, current + 1)
            f.seek(0)
            f.truncate()
            f.write(str(nxt))
            f.flush()
            os.fsync(f.fileno())
            return nxt
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


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
    return sink


def _render_intent_json(intent: MemoryIntent) -> str:
    payload = intent.payload if isinstance(intent.payload, dict) else {}
    doc = {
        "intent_key": str(intent.intent_key or ""),
        "project_id": str(intent.project_id or ""),
        "agent_id": str(intent.agent_id or ""),
        "source_kind": str(intent.source_kind or ""),
        "timestamp": float(intent.timestamp or time.time()),
        "fallback_text": str(intent.fallback_text or ""),
        "payload": payload,
    }
    try:
        return json.dumps(doc, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(intent.fallback_text or "")


def _apply_chronicle_redaction(intent: MemoryIntent, render_vars: dict[str, Any]) -> None:
    key = str(intent.intent_key or "")
    if not key.startswith("tool.read."):
        return
    args = render_vars.get("args", {}) or {}
    path = str(args.get("path", "") or "")
    try:
        start = int(args.get("start") or 1)
    except Exception:
        start = 1
    try:
        end = int(args.get("end") or 0)
    except Exception:
        end = 0
    range_label = f"{start}-EOF" if end <= 0 else f"{start}-{end}"
    result_text = str(render_vars.get("result", "") or "")
    resolved = ""
    m_resolved = re.search(r"resolved_path:\s*(.+)", result_text)
    if m_resolved:
        resolved = str(m_resolved.group(1) or "").strip()
    total = ""
    m_total = re.search(r"total_lines:\s*(\d+)", result_text)
    if m_total:
        total = str(m_total.group(1) or "")
    summary_parts = [f"read path={path}", f"range={range_label}", "content=omitted"]
    if resolved:
        summary_parts.append(f"resolved_path={resolved}")
    if total:
        summary_parts.append(f"total_lines={total}")
    render_vars["result_compact"] = " ".join(summary_parts)


def _render_runtime_fallback(intent: MemoryIntent) -> str:
    summary = str(intent.fallback_text or f"[{intent.source_kind}] {intent.intent_key}").strip()
    payload = intent.payload or {}
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        payload_json = "{}"
    return f"{summary}\n\npayload={payload_json}".strip()


def _render_intent_for_llm_context(intent: MemoryIntent) -> str | None:
    """
    Internal-only context renderer.
    """
    try:
        sink = _resolve_policy(intent)
        if not sink.to_llm_context:
            return None
        return _render_intent_json(intent)
    except Exception:
        return None


def _persist_intent(intent: MemoryIntent) -> dict[str, Any]:
    ts = float(intent.timestamp or time.time())
    intent_seq = _next_intent_seq(intent.project_id, intent.agent_id)
    intent_id = f"{intent.agent_id}:{intent_seq}"
    validate_intent_contract(intent.intent_key, intent.source_kind, intent.payload or {})
    observe_intent_payload(intent.project_id, intent.intent_key, intent.payload or {})
    sink = _resolve_policy(intent)
    chronicle_text = ""
    runtime_text = ""
    if sink.to_chronicle:
        chronicle_text = _render_intent_json(intent)
    if sink.to_runtime_log:
        runtime_text = _render_intent_json(intent)

    llm_context_rendered = _render_intent_for_llm_context(intent)

    chronicle_written = False
    if sink.to_chronicle and str(chronicle_text or "").strip():
        _append_chronicle(intent.project_id, intent.agent_id, chronicle_text)
        append_chronicle_index_entry(
            intent.project_id,
            intent.agent_id,
            {
                "timestamp": ts,
                "intent_key": str(intent.intent_key or ""),
                "source_kind": str(intent.source_kind or ""),
                "source_intent_seq": intent_seq,
                "source_intent_id": intent_id,
                "rendered": str(chronicle_text or ""),
            },
        )
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
                "timestamp": ts,
                "project_id": intent.project_id,
                "agent_id": intent.agent_id,
                "intent_key": intent.intent_key,
                "intent_seq": intent_seq,
                "intent_id": intent_id,
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

    # Single source-of-truth persistence for memory pipeline: raw intent ledger.
    _append_intent(
        intent.project_id,
        intent.agent_id,
        {
            "timestamp": ts,
            "intent_key": str(intent.intent_key or ""),
            "project_id": str(intent.project_id or ""),
            "agent_id": str(intent.agent_id or ""),
            "intent_seq": intent_seq,
            "intent_id": intent_id,
            "source_kind": str(intent.source_kind or ""),
            "payload": dict(intent.payload or {}),
            "fallback_text": str(intent.fallback_text or ""),
            "policy": {
                "to_chronicle": sink.to_chronicle,
                "to_runtime_log": sink.to_runtime_log,
                "to_llm_context": sink.to_llm_context,
                "chronicle_template_key": sink.chronicle_template_key,
                "runtime_log_template_key": sink.runtime_log_template_key,
                "llm_context_template_key": sink.llm_context_template_key,
            },
        },
    )

    # Derived context index (rebuildable): Janus/Chaos read path.
    if llm_context_rendered:
        append_context_index_entry(
            intent.project_id,
            intent.agent_id,
            {
                "timestamp": ts,
                "intent_key": str(intent.intent_key or ""),
                "source_kind": str(intent.source_kind or ""),
                "source_intent_seq": intent_seq,
                "source_intent_id": intent_id,
                "rendered": str(llm_context_rendered or ""),
            },
        )

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
        "intent_seq": intent_seq,
        "intent_id": intent_id,
        "rule": {
            "to_chronicle": decision.policy.to_chronicle,
            "to_runtime_log": decision.policy.to_runtime_log,
            "chronicle_template_key": decision.policy.chronicle_template_key,
            "runtime_log_template_key": decision.policy.runtime_log_template_key,
            "llm_context_template_key": decision.policy.llm_context_template_key,
        },
        "llm_context_rendered": decision.llm_context_rendered,
    }


def record_intent(intent: MemoryIntent) -> dict[str, Any]:
    return _persist_intent(intent)
