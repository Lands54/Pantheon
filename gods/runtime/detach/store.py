"""Detach runtime JSONL store."""
from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path

from gods.runtime.detach.models import DetachJob, DetachStatus


_FINAL_STATES = {DetachStatus.STOPPED, DetachStatus.FAILED, DetachStatus.LOST}


def _runtime_dir(project_id: str) -> Path:
    p = Path("projects") / project_id / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def jobs_path(project_id: str) -> Path:
    return _runtime_dir(project_id) / "detach_jobs.jsonl"


def logs_dir(project_id: str) -> Path:
    p = _runtime_dir(project_id) / "detach_logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _lock_path(project_id: str) -> Path:
    d = _runtime_dir(project_id) / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return d / "detach_jobs.lock"


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _write_rows(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _with_lock(project_id: str, mutator):
    lock = _lock_path(project_id)
    lock.touch(exist_ok=True)
    with open(lock, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            path = jobs_path(project_id)
            rows = _read_rows(path)
            rows2, result = mutator(rows)
            _write_rows(path, rows2)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def create_job(project_id: str, agent_id: str, command: str) -> DetachJob:
    now = time.time()
    job_id = uuid.uuid4().hex
    log = str((logs_dir(project_id) / f"{job_id}.log").as_posix())
    job = DetachJob(
        job_id=job_id,
        project_id=project_id,
        agent_id=agent_id,
        command=command,
        created_at=now,
        status=DetachStatus.QUEUED,
        log_path=log,
    )

    def _m(rows):
        rows.append(job.to_dict())
        return rows, job

    return _with_lock(project_id, _m)


def list_jobs(project_id: str, agent_id: str | None = None, status: DetachStatus | None = None, limit: int = 100) -> list[DetachJob]:
    rows = _read_rows(jobs_path(project_id))
    out = []
    for row in rows:
        if agent_id and str(row.get("agent_id", "")) != agent_id:
            continue
        if status and str(row.get("status", "")) != status.value:
            continue
        out.append(DetachJob.from_dict(row))
    out.sort(key=lambda x: x.created_at)
    return out[-max(1, limit) :]


def get_job(project_id: str, job_id: str) -> DetachJob | None:
    rows = _read_rows(jobs_path(project_id))
    for row in rows:
        if str(row.get("job_id", "")) == job_id:
            return DetachJob.from_dict(row)
    return None


def update_job(project_id: str, job_id: str, **fields) -> DetachJob | None:
    now = time.time()

    def _m(rows):
        found = None
        for row in rows:
            if str(row.get("job_id", "")) != job_id:
                continue
            for k, v in fields.items():
                row[k] = v
            if "status" in fields:
                sv = str(fields["status"])
                if sv in {DetachStatus.STOPPED.value, DetachStatus.FAILED.value, DetachStatus.LOST.value}:
                    row["ended_at"] = row.get("ended_at") or now
            found = DetachJob.from_dict(row)
            break
        return rows, found

    return _with_lock(project_id, _m)


def transition_job(project_id: str, job_id: str, target: DetachStatus, stop_reason: str = "", exit_code: int | None = None) -> DetachJob | None:
    now = time.time()

    def _m(rows):
        found = None
        for row in rows:
            if str(row.get("job_id", "")) != job_id:
                continue
            row["status"] = target.value
            if target == DetachStatus.RUNNING:
                row["started_at"] = row.get("started_at") or now
            if target in _FINAL_STATES:
                row["ended_at"] = row.get("ended_at") or now
            if stop_reason:
                row["stop_reason"] = stop_reason
            if exit_code is not None:
                row["exit_code"] = int(exit_code)
            found = DetachJob.from_dict(row)
            break
        return rows, found

    return _with_lock(project_id, _m)


def mark_non_final_as_lost(project_id: str) -> int:
    now = time.time()

    def _m(rows):
        count = 0
        for row in rows:
            status = str(row.get("status", ""))
            if status in {x.value for x in _FINAL_STATES}:
                continue
            row["status"] = DetachStatus.LOST.value
            row["stop_reason"] = "startup_lost"
            row["ended_at"] = row.get("ended_at") or now
            count += 1
        return rows, count

    return int(_with_lock(project_id, _m) or 0)


def append_log(project_id: str, job_id: str, text: str, tail_chars: int):
    p = logs_dir(project_id) / f"{job_id}.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(text)
    max_chars = max(1000, int(tail_chars) * 4)
    try:
        content = p.read_text(encoding="utf-8")
        if len(content) > max_chars:
            p.write_text(content[-max(200, int(tail_chars) * 2) :], encoding="utf-8")
    except Exception:
        pass


def read_log_tail(project_id: str, job_id: str, tail_chars: int) -> str:
    p = logs_dir(project_id) / f"{job_id}.log"
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8")
    return txt[-max(200, int(tail_chars)) :]
