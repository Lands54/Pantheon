#!/usr/bin/env python3
"""One-shot migration of legacy event/task files into unified events.jsonl bus."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from gods.events.models import EventRecord
from gods.events.store import append_event, events_path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _mark_backup(path: Path):
    if not path.exists():
        return
    ts = int(time.time())
    bak = path.with_suffix(path.suffix + f".bak.{ts}")
    shutil.move(str(path), str(bak))


def _append(project_id: str, domain: str, event_type: str, priority: int, payload: dict, row: dict):
    rec = EventRecord.create(
        project_id=project_id,
        domain=domain,
        event_type=event_type,
        priority=priority,
        payload=payload,
        dedupe_key=str(row.get("dedupe_key", "")),
        max_attempts=int(row.get("max_attempts", 3) or 3),
        event_id=str(row.get("event_id", "") or None),
        meta={"migrated": True},
    )
    rec.state = rec.state if str(row.get("state", "")) == "" else rec.state.__class__(str(row.get("state", "queued")))
    rec.created_at = float(row.get("created_at", time.time()) or time.time())
    rec.available_at = float(row.get("available_at", rec.created_at) or rec.created_at)
    rec.picked_at = float(row.get("picked_at")) if row.get("picked_at") is not None else None
    rec.done_at = float(row.get("done_at")) if row.get("done_at") is not None else None
    rec.attempt = int(row.get("attempt", 0) or 0)
    rec.error_code = str(row.get("error_code", ""))
    rec.error_message = str(row.get("error_message", ""))
    append_event(rec)


def migrate_project(project_id: str) -> dict:
    rt = Path("projects") / project_id / "runtime"
    proto = Path("projects") / project_id / "protocols"
    out = events_path(project_id)
    if out.exists() and out.stat().st_size > 0:
        return {"project_id": project_id, "status": "skipped", "reason": "already_migrated", "count": 0}

    count = 0
    sources = [
        rt / "mail_events.jsonl",
        rt / "angelia_events.jsonl",
        rt / "pulse_events.jsonl",
        rt / "detach_jobs.jsonl",
        proto / "invocations.jsonl",
    ]

    for row in _read_jsonl(rt / "mail_events.jsonl"):
        _append(project_id, "iris", str(row.get("event_type", "mail_event")), int(row.get("priority", 100)), row.get("payload") or {}, row)
        count += 1
    for row in _read_jsonl(rt / "angelia_events.jsonl"):
        _append(project_id, "angelia", str(row.get("event_type", "system_event")), int(row.get("priority", 50)), row.get("payload") or {}, row)
        count += 1
    for row in _read_jsonl(rt / "pulse_events.jsonl"):
        et = str(row.get("event_type", "system"))
        mapped = {
            "inbox_event": "mail_event",
            "mail_event": "mail_event",
            "timer": "timer_event",
            "manual": "manual_event",
            "system": "system_event",
        }.get(et, "system_event")
        _append(project_id, "angelia", mapped, int(row.get("priority", 50)), row.get("payload") or {}, row)
        count += 1
    for row in _read_jsonl(rt / "detach_jobs.jsonl"):
        st = str(row.get("status", "queued"))
        mapped = {
            "queued": "detach_submitted_event",
            "running": "detach_started_event",
            "stopping": "detach_stopping_event",
            "stopped": "detach_stopped_event",
            "failed": "detach_failed_event",
            "lost": "detach_lost_event",
        }.get(st, "detach_submitted_event")
        payload = {
            "agent_id": row.get("agent_id", ""),
            "job_id": row.get("job_id", ""),
            "command": row.get("command", ""),
            "status": st,
            "exit_code": row.get("exit_code"),
        }
        _append(project_id, "runtime", mapped, 40, payload, row)
        count += 1
    for row in _read_jsonl(proto / "invocations.jsonl"):
        payload = {
            "name": row.get("name", ""),
            "caller_id": row.get("caller_id", ""),
            "ok": row.get("ok", False),
            "mode": row.get("mode", "sync"),
            "status": row.get("status", ""),
        }
        _append(project_id, "hermes", "hermes_protocol_invoked_event", 30, payload, row)
        count += 1

    for src in sources:
        _mark_backup(src)
    return {"project_id": project_id, "status": "migrated", "count": count}


def main() -> int:
    root = Path("projects")
    if not root.exists():
        print(json.dumps({"projects": [], "migrated": 0}, ensure_ascii=False))
        return 0
    rows = []
    migrated = 0
    for p in sorted([x for x in root.iterdir() if x.is_dir()]):
        r = migrate_project(p.name)
        rows.append(r)
        if r.get("status") == "migrated":
            migrated += 1
    print(json.dumps({"projects": rows, "migrated": migrated}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
