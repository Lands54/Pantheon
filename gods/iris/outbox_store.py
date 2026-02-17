"""Outbox receipt JSONL store with project-local file locking."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.iris.outbox_models import OutboxReceipt, OutboxReceiptStatus
from gods.paths import runtime_dir, runtime_locks_dir


def _runtime_dir(project_id: str) -> Path:
    path = runtime_dir(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _receipts_path(project_id: str) -> Path:
    return _runtime_dir(project_id) / "outbox_receipts.jsonl"


def _lock_path(project_id: str) -> Path:
    lock_dir = runtime_locks_dir(project_id)
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "outbox_receipts.lock"


def _read_all_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _write_all_rows(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _with_locked_rows(project_id: str, mutator):
    lock = _lock_path(project_id)
    lock.touch(exist_ok=True)
    receipts = _receipts_path(project_id)
    with open(lock, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rows = _read_all_rows(receipts)
            new_rows, result = mutator(rows)
            _write_all_rows(receipts, new_rows)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def create_receipt(
    project_id: str,
    from_agent_id: str,
    to_agent_id: str,
    title: str,
    message_id: str,
    status: OutboxReceiptStatus = OutboxReceiptStatus.PENDING,
    error_message: str = "",
) -> OutboxReceipt:
    now = time.time()
    receipt = OutboxReceipt(
        receipt_id=uuid.uuid4().hex,
        project_id=project_id,
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        title=title,
        message_id=message_id,
        status=status,
        created_at=now,
        updated_at=now,
        error_message=str(error_message or ""),
    )

    def _mut(rows: list[dict]):
        rows.append(receipt.to_dict())
        return rows, receipt

    return _with_locked_rows(project_id, _mut)


def update_status_by_message_id(
    project_id: str,
    message_id: str,
    status: OutboxReceiptStatus,
    error_message: str = "",
) -> list[OutboxReceipt]:
    now = time.time()
    mid = str(message_id or "").strip()
    if not mid:
        return []

    def _mut(rows: list[dict]):
        changed_rows: list[dict] = []
        for row in rows:
            if str(row.get("message_id", "")) != mid:
                continue
            row["status"] = status.value
            row["updated_at"] = now
            if status == OutboxReceiptStatus.FAILED:
                row["error_message"] = str(error_message or "")[:2000]
            changed_rows.append(dict(row))
        return rows, changed_rows

    rows = list(_with_locked_rows(project_id, _mut) or [])
    return [OutboxReceipt.from_dict(r) for r in rows]


def list_receipts(
    project_id: str,
    from_agent_id: str = "",
    to_agent_id: str = "",
    status: str = "",
    message_id: str = "",
    limit: int = 100,
) -> list[OutboxReceipt]:
    rows = _read_all_rows(_receipts_path(project_id))
    out: list[OutboxReceipt] = []
    for row in rows:
        if from_agent_id and str(row.get("from_agent_id", "")) != from_agent_id:
            continue
        if to_agent_id and str(row.get("to_agent_id", "")) != to_agent_id:
            continue
        if status and str(row.get("status", "")) != status:
            continue
        if message_id and str(row.get("message_id", "")) != message_id:
            continue
        out.append(OutboxReceipt.from_dict(row))
    out.sort(key=lambda x: x.updated_at, reverse=True)
    return out[: max(1, min(limit, 1000))]
