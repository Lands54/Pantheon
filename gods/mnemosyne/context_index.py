"""Mnemosyne context index (derived, rebuildable).

This is a write-time derived index from MemoryIntent, used by Janus/Chaos
for fast context assembly without re-rendering every intent payload.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gods.mnemosyne.policy_registry import load_memory_policy
from gods.mnemosyne.template_registry import render_memory_template
from gods.paths import mnemosyne_dir


def _index_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "context_index" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _intents_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "intents" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _render_llm_context_from_intent_row(project_id: str, row: dict[str, Any], policy_map: dict[str, dict[str, Any]]) -> str:
    intent_key = str(row.get("intent_key", "") or "").strip()
    if not intent_key:
        return ""
    rule = policy_map.get(intent_key) or {}
    if not bool(rule.get("to_llm_context", False)):
        return ""
    tpl = str(rule.get("llm_context_template_key", "") or "").strip()
    if not tpl:
        return str(row.get("fallback_text", "") or "").strip()
    payload = row.get("payload")
    render_vars = dict(payload) if isinstance(payload, dict) else {}
    render_vars.setdefault("project_id", str(row.get("project_id", "") or ""))
    render_vars.setdefault("agent_id", str(row.get("agent_id", "") or ""))
    render_vars.setdefault("intent_key", intent_key)
    try:
        return str(render_memory_template(project_id, "llm_context", tpl, render_vars) or "").strip()
    except Exception:
        return str(row.get("fallback_text", "") or "").strip()


def rebuild_context_index_from_intents(project_id: str, agent_id: str, limit: int = 5000) -> dict[str, Any]:
    intents_path = _intents_path(project_id, agent_id)
    idx_path = _index_path(project_id, agent_id)
    policy_map = load_memory_policy(project_id)
    rows: list[dict[str, Any]] = []
    if intents_path.exists():
        with intents_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    if limit > 0:
        rows = rows[-max(1, min(int(limit), 50000)) :]
    rebuilt_rows: list[dict[str, Any]] = []
    for row in rows:
        rendered = _render_llm_context_from_intent_row(project_id, row, policy_map)
        if not rendered:
            continue
        rebuilt_rows.append(
            {
                "timestamp": float(row.get("timestamp") or 0.0),
                "intent_key": str(row.get("intent_key", "") or ""),
                "source_kind": str(row.get("source_kind", "") or ""),
                "source_intent_seq": row.get("intent_seq"),
                "source_intent_id": str(row.get("intent_id", "") or ""),
                "rendered": rendered,
            }
        )
    tmp = idx_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rebuilt_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(idx_path)
    return {
        "project_id": project_id,
        "agent_id": agent_id,
        "source_intents": len(rows),
        "rows": len(rebuilt_rows),
        "path": str(idx_path),
    }


def append_context_index_entry(project_id: str, agent_id: str, row: dict[str, Any]) -> None:
    path = _index_path(project_id, agent_id)
    payload = dict(row or {})
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_context_index_entries(project_id: str, agent_id: str, limit: int = 200) -> list[dict[str, Any]]:
    path = _index_path(project_id, agent_id)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    if limit <= 0:
        return []
    return rows[-max(1, min(int(limit), 5000)) :]


def list_context_index_texts(project_id: str, agent_id: str, limit: int = 200) -> list[str]:
    out: list[str] = []
    for row in list_context_index_entries(project_id, agent_id, limit=limit):
        text = str(row.get("rendered", "") or "").strip()
        if text:
            out.append(text)
    return out
