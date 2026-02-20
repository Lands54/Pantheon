"""Janus context cards + latest-only snapshot persistence."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Literal, TypedDict

from gods.paths import mnemosyne_dir


CardKind = Literal["task", "event", "mailbox", "tool", "chronicle_summary", "policy", "derived"]
CHAOS_CARD_BUCKET_KEYS: tuple[str, ...] = (
    "profile",
    "task_state",
    "mailbox",
    "events",
    "policy",
)


class ContextCard(TypedDict):
    card_id: str
    kind: CardKind
    text: str
    source_intent_ids: list[str]
    source_intent_seq_max: int
    derived_from_card_ids: list[str]
    supersedes_card_ids: list[str]
    compression_type: str
    meta: dict[str, Any]
    created_at: float


class JanusSnapshot(TypedDict):
    snapshot_id: str
    project_id: str
    agent_id: str
    base_intent_seq: int
    token_estimate: int
    cards: list[ContextCard]
    dropped: list[dict[str, Any]]
    created_at: float
    updated_at: float


_REQUIRED_CARD_FIELDS: tuple[str, ...] = (
    "card_id",
    "kind",
    "text",
    "source_intent_ids",
    "source_intent_seq_max",
    "derived_from_card_ids",
    "supersedes_card_ids",
    "compression_type",
    "meta",
    "created_at",
)
from gods.mnemosyne.semantics import semantics_service


def _snapshot_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "janus_snapshot" / f"{agent_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _compression_log_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "janus_snapshot" / "compression_logs" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _derived_log_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "janus_snapshot" / "derived" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _intents_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "intents" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _context_index_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "context_index" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _chronicle_index_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "chronicle_index" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _is_declared_material_without_intent(card_id: str) -> bool:
    return semantics_service.is_valid_material(card_id)


def validate_context_card(card: dict[str, Any]) -> None:
    if not isinstance(card, dict):
        raise ValueError("card must be object")
    missing = [k for k in _REQUIRED_CARD_FIELDS if k not in card]
    if missing:
        raise ValueError(f"card missing required field(s): {', '.join(missing)}")
    if not str(card.get("card_id", "") or "").strip():
        raise ValueError("card.card_id is required")
    kind = str(card.get("kind", "") or "").strip()
    if kind not in {"task", "event", "mailbox", "tool", "chronicle_summary", "policy", "derived"}:
        raise ValueError(f"card.kind invalid: {kind}")
    if not isinstance(card.get("source_intent_ids"), list):
        raise ValueError("card.source_intent_ids must be list")
    source_ids = [str(x).strip() for x in list(card.get("source_intent_ids", []) or []) if str(x).strip()]
    
    # Use semantics_service instead of old material_cards_registry.json
    if not source_ids and not semantics_service.is_valid_material(str(card.get("card_id", "") or "")):
        raise ValueError(
            f"card.source_intent_ids is empty and card_id '{card.get('card_id')}' is not declared in semantics.json"
        )
    if not isinstance(card.get("derived_from_card_ids"), list):
        raise ValueError("card.derived_from_card_ids must be list")
    if not isinstance(card.get("supersedes_card_ids"), list):
        raise ValueError("card.supersedes_card_ids must be list")
    if not isinstance(card.get("meta"), dict):
        raise ValueError("card.meta must be object")
    _ = int(card.get("source_intent_seq_max", 0) or 0)
    _ = float(card.get("created_at", 0.0) or 0.0)


def validate_card_buckets(card_buckets: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(card_buckets, dict):
        raise ValueError("card_buckets must be object")
    keys = set(card_buckets.keys())
    required = set(CHAOS_CARD_BUCKET_KEYS)
    if keys != required:
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        detail: list[str] = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if extra:
            detail.append(f"extra={','.join(extra)}")
        raise ValueError(f"card_buckets key mismatch: {'; '.join(detail)}")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key in CHAOS_CARD_BUCKET_KEYS:
        rows = card_buckets.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"card_buckets.{key} must be list")
        out_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"card_buckets.{key} item must be object")
            validate_context_card(row)
            out_rows.append(dict(row))
        normalized[key] = out_rows
    return normalized


def _tok_len(text: str) -> int:
    return max(1, len(str(text or "")) // 4)


def estimate_cards_tokens(cards: list[dict[str, Any]] | None) -> int:
    total = 0
    for c in list(cards or []):
        total += _tok_len(str((c or {}).get("text", "") or ""))
    return int(total)


def load_janus_snapshot(project_id: str, agent_id: str) -> JanusSnapshot | None:
    path = _snapshot_path(project_id, agent_id)
    if not path.exists():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    cards_raw = row.get("cards", [])
    if not isinstance(cards_raw, list):
        return None
    cards: list[ContextCard] = []
    for item in cards_raw:
        if not isinstance(item, dict):
            continue
        try:
            validate_context_card(item)
            cards.append(ContextCard(**dict(item)))
        except Exception:
            continue
    return JanusSnapshot(
        snapshot_id=str(row.get("snapshot_id", "") or ""),
        project_id=str(row.get("project_id", project_id) or project_id),
        agent_id=str(row.get("agent_id", agent_id) or agent_id),
        base_intent_seq=_to_int(row.get("base_intent_seq"), 0),
        token_estimate=_to_int(row.get("token_estimate"), 0),
        cards=cards,
        dropped=list(row.get("dropped", []) or []),
        created_at=float(row.get("created_at") or 0.0),
        updated_at=float(row.get("updated_at") or 0.0),
    )


def save_janus_snapshot(project_id: str, agent_id: str, snapshot: JanusSnapshot | dict[str, Any]) -> dict[str, Any]:
    path = _snapshot_path(project_id, agent_id)
    lock_path = path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(snapshot or {})
    payload["project_id"] = project_id
    payload["agent_id"] = agent_id
    now = time.time()
    if float(payload.get("created_at") or 0.0) <= 0:
        payload["created_at"] = now
    payload["updated_at"] = now
    tmp = path.with_suffix(".json.tmp")
    with lock_path.open("a+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
            os.fsync(lf.fileno())
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    return {"project_id": project_id, "agent_id": agent_id, "path": str(path), "snapshot_id": str(payload.get("snapshot_id", ""))}


def _kind_from_intent(intent_key: str) -> CardKind:
    k = str(intent_key or "")
    if k.startswith("tool."):
        return "tool"
    if k.startswith("inbox.") or k.startswith("outbox."):
        return "mailbox"
    if k.startswith("event."):
        return "event"
    if k.startswith("agent.") or k.startswith("phase."):
        return "policy"
    if k == "llm.response":
        return "chronicle_summary"
    return "event"


def _kind_from_intent(intent_key: str) -> CardKind:
    k = str(intent_key or "")
    if k.startswith("tool."):
        return "tool"
    if k.startswith("inbox.") or k.startswith("outbox."):
        return "mailbox"
    if k.startswith("event."):
        return "event"
    if k.startswith("agent.") or k.startswith("phase."):
        return "policy"
    if k == "llm.response":
        return "chronicle_summary"
    return "event"


def _card_id_for_row(row: dict[str, Any]) -> str:
    key = str(row.get("intent_key", "") or "")
    payload = row.get("payload")
    data = payload if isinstance(payload, dict) else {}
    if key.startswith("tool.call."):
        tn = str(data.get("tool_name", "") or "")
        cid = str(data.get("call_id", "") or "")
        return f"tool.call:{tn}:{cid or 'unknown'}"
    if key.startswith("tool."):
        tn = str(data.get("tool_name", "") or "")
        st = str(data.get("status", "") or "")
        cid = str(data.get("call_id", "") or "")
        suffix = f":{cid}" if cid else ""
        return f"tool:{tn}:{st}{suffix}"
    if key.startswith("inbox.") or key.startswith("outbox."):
        mid = str(data.get("message_id", "") or "")
        sec = str(data.get("section", "") or "")
        return f"mailbox:{mid or sec or key}"
    if key.startswith("event."):
        et = str(data.get("event_type", "") or key)
        return f"event:{et}"
    if key == "llm.response":
        return "chronicle:llm.response"
    fp = hashlib.sha1(f"{key}|{json.dumps(data, ensure_ascii=False, sort_keys=True)}".encode("utf-8")).hexdigest()[:10]
    return f"intent:{key}:{fp}"


def _card_text_for_row(row: dict[str, Any]) -> str:
    txt = str(row.get("fallback_text", "") or "").strip()
    if txt:
        return txt
    payload = row.get("payload")
    if isinstance(payload, dict) and payload:
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(payload)
    return f"[{str(row.get('intent_key', 'unknown'))}]"


def build_cards_from_intents(
    project_id: str,
    agent_id: str,
    from_intent_seq: int,
    to_intent_seq: int = 0,
    limit: int = 1000,
) -> list[ContextCard]:
    path = _intents_path(project_id, agent_id)
    if not path.exists():
        return []
    min_seq = max(0, int(from_intent_seq or 0))
    max_seq = int(to_intent_seq or 0)
    rows: list[ContextCard] = []
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
            seq = _to_int(row.get("intent_seq"), 0)
            if seq <= min_seq:
                continue
            if max_seq > 0 and seq > max_seq:
                continue
            key = str(row.get("intent_key", "") or "")
            if not key:
                continue
            iid = str(row.get("intent_id", "") or "").strip() or f"{agent_id}:{seq}"
            kind = _kind_from_intent(key)
            rows.append(
                ContextCard(
                    card_id=_card_id_for_row(row),
                    kind=kind,
                    text=_card_text_for_row(row),
                    source_intent_ids=[iid],
                    source_intent_seq_max=max(0, seq),
                    derived_from_card_ids=[],
                    supersedes_card_ids=[],
                    compression_type="",
                    meta={"intent_key": key, "source_kind": str(row.get("source_kind", "") or "")},
                    created_at=float(row.get("timestamp") or time.time()),
                )
            )
    if limit > 0:
        rows = rows[-max(1, min(int(limit), 20000)) :]
    return rows


def _read_index_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _card_from_index_row(row: dict[str, Any], *, memory_span: str) -> ContextCard | None:
    intent_key = str(row.get("intent_key", "") or "").strip()
    if not intent_key:
        return None
    rendered = str(row.get("rendered", "") or "").strip()
    if not rendered:
        return None
    src_id = str(row.get("source_intent_id", "") or "").strip()
    src_seq = _to_int(row.get("source_intent_seq"), 0)
    if not src_id and src_seq > 0:
        src_id = f"intent:{src_seq}"
    if not src_id:
        return None
    kind = _kind_from_intent(intent_key)
    card_id = f"intent.{memory_span}:{src_id}"
    return ContextCard(
        card_id=card_id,
        kind=kind,
        text=rendered,
        source_intent_ids=[src_id],
        source_intent_seq_max=max(0, src_seq),
        derived_from_card_ids=[],
        supersedes_card_ids=[],
        compression_type="",
        meta={
            "intent_key": intent_key,
            "source_kind": str(row.get("source_kind", "") or ""),
            "memory_span": memory_span,
        },
        created_at=float(row.get("timestamp") or time.time()),
    )


def build_cards_from_intent_views(
    project_id: str,
    agent_id: str,
    split_intent_seq: int,
    to_intent_seq: int = 0,
    long_limit: int = 4000,
    short_limit: int = 2000,
) -> list[ContextCard]:
    """
    Build semantic cards from intent-derived views:
    - long view: chronicle_index rows with source_intent_seq <= split_intent_seq
    - short view: context_index rows with source_intent_seq > split_intent_seq
    """
    split_seq = max(0, int(split_intent_seq or 0))
    max_seq = int(to_intent_seq or 0)
    out: list[ContextCard] = []

    long_rows = _read_index_rows(_chronicle_index_path(project_id, agent_id))
    for row in long_rows:
        seq = _to_int(row.get("source_intent_seq"), 0)
        if seq <= 0 or seq > split_seq:
            continue
        card = _card_from_index_row(row, memory_span="long")
        if card is not None:
            out.append(card)
    if long_limit > 0:
        out = out[-max(1, min(int(long_limit), 50000)) :]

    short_rows = _read_index_rows(_context_index_path(project_id, agent_id))
    short_cards: list[ContextCard] = []
    for row in short_rows:
        seq = _to_int(row.get("source_intent_seq"), 0)
        if seq <= split_seq:
            continue
        if max_seq > 0 and seq > max_seq:
            continue
        card = _card_from_index_row(row, memory_span="short")
        if card is not None:
            short_cards.append(card)
    if short_limit > 0:
        short_cards = short_cards[-max(1, min(int(short_limit), 50000)) :]

    # Fallback for short window if context-index has no rows yet.
    if not short_cards:
        short_cards = build_cards_from_intents(
            project_id,
            agent_id,
            from_intent_seq=split_seq,
            to_intent_seq=max_seq,
            limit=short_limit,
        )
        for c in short_cards:
            meta = dict(c.get("meta", {}) or {})
            meta["memory_span"] = "short"
            c["meta"] = meta
            c["card_id"] = f"intent.short:{str(c.get('source_intent_ids', [''])[0] or c.get('card_id', 'unknown'))}"

    out.extend(short_cards)
    out.sort(
        key=lambda x: (
            int(x.get("source_intent_seq_max", 0) or 0),
            float(x.get("created_at", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return out


def latest_intent_seq(project_id: str, agent_id: str) -> int:
    path = _intents_path(project_id, agent_id)
    if not path.exists():
        return 0
    last = 0
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
            seq = _to_int(row.get("intent_seq"), 0)
            if seq > last:
                last = seq
    return int(last)


def record_snapshot_compression(project_id: str, agent_id: str, row: dict[str, Any]) -> dict[str, Any]:
    path = _compression_log_path(project_id, agent_id)
    payload = dict(row or {})
    payload["project_id"] = project_id
    payload["agent_id"] = agent_id
    payload["timestamp"] = float(payload.get("timestamp") or time.time())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _record_derived_rows(project_id, agent_id, payload)
    return {"project_id": project_id, "agent_id": agent_id, "path": str(path)}


def list_snapshot_compressions(project_id: str, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    path = _compression_log_path(project_id, agent_id)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    if limit <= 0:
        return []
    return out[-max(1, min(int(limit), 5000)) :]


def _record_derived_rows(project_id: str, agent_id: str, compression_row: dict[str, Any]) -> None:
    rows = list(compression_row.get("derived", []) or [])
    if not rows:
        return
    path = _derived_log_path(project_id, agent_id)
    base = {
        "project_id": project_id,
        "agent_id": agent_id,
        "snapshot_id": str(compression_row.get("snapshot_id", "") or ""),
        "base_intent_seq": int(compression_row.get("base_intent_seq", 0) or 0),
        "before_tokens": int(compression_row.get("before_tokens", 0) or 0),
        "after_tokens": int(compression_row.get("after_tokens", 0) or 0),
        "timestamp": float(compression_row.get("timestamp") or time.time()),
    }
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = dict(base)
            payload["derived_card"] = {
                "card_id": str(row.get("card_id", "") or ""),
                "derived_from_card_ids": [str(x) for x in list(row.get("derived_from_card_ids", []) or []) if str(x).strip()],
                "supersedes_card_ids": [str(x) for x in list(row.get("supersedes_card_ids", []) or []) if str(x).strip()],
                "source_intent_ids": [str(x) for x in list(row.get("source_intent_ids", []) or []) if str(x).strip()],
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_derived_cards(project_id: str, agent_id: str, limit: int = 100) -> list[dict[str, Any]]:
    path = _derived_log_path(project_id, agent_id)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    if limit <= 0:
        return []
    return out[-max(1, min(int(limit), 10000)) :]
