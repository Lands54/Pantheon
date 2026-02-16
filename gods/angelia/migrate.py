"""Migration helpers from legacy pulse/inbox files to Angelia events."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import policy, store
from gods.angelia.models import AngeliaEvent, AngeliaEventState


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def migrate_to_angelia(project_id: str) -> dict:
    rt = Path("projects") / project_id / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    target = store.events_path(project_id)
    if target.exists() and target.stat().st_size > 0:
        return {"project_id": project_id, "status": "skipped", "reason": "already_migrated", "events": 0}

    pulse_file = rt / "pulse_events.jsonl"
    inbox_file = rt / "inbox_events.jsonl"

    rows: list[dict] = []
    now = time.time()

    for row in _read_jsonl(pulse_file):
        st = str(row.get("status", "queued"))
        if st not in {"queued", "picked"}:
            continue
        created = float(row.get("created_at", now) or now)
        ev = AngeliaEvent(
            event_id=str(row.get("event_id") or ""),
            project_id=project_id,
            agent_id=str(row.get("agent_id", "")),
            event_type=str(row.get("event_type", "system")),
            priority=int(row.get("priority", 0)),
            state=AngeliaEventState.QUEUED,
            payload=row.get("payload") or {},
            attempt=0,
            max_attempts=policy.event_max_attempts(project_id),
            created_at=created,
            available_at=created,
        )
        if ev.event_id and ev.agent_id:
            rows.append(ev.to_dict())

    for row in _read_jsonl(inbox_file):
        st = str(row.get("state", "pending"))
        if st not in {"pending", "deferred"}:
            continue
        created = float(row.get("created_at", now) or now)
        ev = AngeliaEvent(
            event_id=f"mig_inbox_{str(row.get('event_id', ''))}",
            project_id=project_id,
            agent_id=str(row.get("agent_id", "")),
            event_type="inbox_event",
            priority=policy.default_priority(project_id, "inbox_event"),
            state=AngeliaEventState.QUEUED,
            payload={
                "inbox_event_id": str(row.get("event_id", "")),
                "sender": str(row.get("sender", "")),
                "message": str(row.get("content", "")),
                "msg_type": str(row.get("msg_type", "private")),
            },
            dedupe_key=f"inbox:{str(row.get('event_id', ''))}",
            attempt=0,
            max_attempts=policy.event_max_attempts(project_id),
            created_at=created,
            available_at=created,
        )
        if ev.agent_id:
            rows.append(ev.to_dict())

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    ts = int(time.time())
    for legacy in (pulse_file, inbox_file):
        if legacy.exists():
            bak = legacy.with_suffix(legacy.suffix + f".bak.{ts}")
            shutil.move(str(legacy), str(bak))

    return {"project_id": project_id, "status": "migrated", "events": len(rows)}
