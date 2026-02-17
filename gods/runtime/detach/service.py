"""Detach orchestration service."""
from __future__ import annotations

import shlex
import time
from pathlib import Path
from urllib.parse import urlparse

from gods.config import runtime_config
from gods.runtime.detach.models import DetachStatus
from gods.runtime.detach.events import emit_detach_event
from gods.runtime.detach.policy import select_fifo_victims
from gods.runtime.detach.runner import stop_job
from gods.runtime.detach.store import (
    create_job,
    get_job,
    list_jobs,
    mark_non_final_as_lost,
    read_log_tail,
)
from gods.runtime.detach.runner import start_job

SAFE_BASE_COMMANDS = {
    "python",
    "python3",
    "pytest",
    "uv",
    "ls",
    "cat",
    "pwd",
    "echo",
    "find",
    "rg",
    "grep",
    "sed",
    "head",
    "tail",
    "mkdir",
    "touch",
    "cp",
    "curl",
}
LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1"}


class DetachError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _is_localhost_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in LOCALHOST_NAMES


def _validate_command(command: str):
    if any(c in command for c in [";", "&", "|", ">", "<", "`", "$"]):
        raise DetachError("DETACH_COMMAND_INVALID", "forbidden shell chaining symbols")
    try:
        parts = shlex.split(command)
    except Exception as e:
        raise DetachError("DETACH_COMMAND_INVALID", f"invalid syntax: {e}") from e

    if not parts:
        raise DetachError("DETACH_COMMAND_INVALID", "empty command")

    base = Path(parts[0]).name.lower()
    if base not in SAFE_BASE_COMMANDS:
        raise DetachError("DETACH_COMMAND_INVALID", f"command '{base}' is not allowed")

    if base in {"pip", "pip3"}:
        raise DetachError("DETACH_COMMAND_INVALID", "plain pip/pip3 is forbidden")

    if base == "curl":
        urls = [p for p in parts[1:] if p.startswith("http://") or p.startswith("https://")]
        if not urls:
            raise DetachError("DETACH_COMMAND_INVALID", "curl requires localhost URL")
        for u in urls:
            if not _is_localhost_url(u):
                raise DetachError("DETACH_COMMAND_INVALID", f"curl url blocked: {u}")


def _project_cfg(project_id: str):
    proj = runtime_config.projects.get(project_id)
    if not proj:
        raise DetachError("DETACH_PROJECT_NOT_FOUND", f"project '{project_id}' not found")
    return proj


def _backend_guard(project_id: str):
    proj = _project_cfg(project_id)
    if not bool(getattr(proj, "detach_enabled", True)):
        raise DetachError("DETACH_DISABLED", "detach is disabled by project policy")
    if str(getattr(proj, "command_executor", "local")) != "docker" or not bool(getattr(proj, "docker_enabled", True)):
        raise DetachError("DETACH_BACKEND_UNSUPPORTED", "detach requires command_executor=docker and docker_enabled=true")


def _max_running_agent(project_id: str) -> int:
    return max(1, int(getattr(_project_cfg(project_id), "detach_max_running_per_agent", 2)))


def _max_running_project(project_id: str) -> int:
    return max(1, int(getattr(_project_cfg(project_id), "detach_max_running_per_project", 8)))


def _max_queue_agent(project_id: str) -> int:
    return max(1, int(getattr(_project_cfg(project_id), "detach_queue_max_per_agent", 8)))


def _ttl(project_id: str) -> int:
    return max(30, int(getattr(_project_cfg(project_id), "detach_ttl_sec", 1800)))


def _grace(project_id: str) -> int:
    return max(1, int(getattr(_project_cfg(project_id), "detach_stop_grace_sec", 10)))


def _log_tail(project_id: str) -> int:
    return max(500, int(getattr(_project_cfg(project_id), "detach_log_tail_chars", 4000)))


def submit(project_id: str, agent_id: str, command: str) -> dict:
    _backend_guard(project_id)
    _validate_command(command)

    jobs_agent = list_jobs(project_id, agent_id=agent_id, limit=1000)
    queued_count = sum(1 for j in jobs_agent if j.status == DetachStatus.QUEUED)
    if queued_count >= _max_queue_agent(project_id):
        raise DetachError("DETACH_QUEUE_FULL", f"agent queue full ({queued_count})")

    job = create_job(project_id, agent_id, command)
    started = start_job(project_id, job.job_id, agent_id, command, _log_tail(project_id))
    if not started:
        raise DetachError("DETACH_RUNNER_ERROR", "runner start failed")
    try:
        emit_detach_event(
            project_id,
            "detach_submitted_event",
            payload={
                "job_id": job.job_id,
                "agent_id": agent_id,
                "command": command,
                "status": "queued",
            },
            dedupe_key=f"detach_submitted:{job.job_id}",
        )
    except Exception:
        pass

    reconcile(project_id)
    return {"ok": True, "job_id": job.job_id, "status": "queued", "project_id": project_id, "agent_id": agent_id}


def list_for_api(project_id: str, agent_id: str = "", status: str = "", limit: int = 50) -> dict:
    _project_cfg(project_id)
    st = None
    if status:
        st = DetachStatus(status)
    rows = list_jobs(project_id, agent_id=(agent_id or None), status=st, limit=max(1, min(limit, 500)))
    return {"project_id": project_id, "items": [r.to_dict() for r in rows]}


def stop(project_id: str, job_id: str, reason: str = "manual") -> dict:
    _backend_guard(project_id)
    item = get_job(project_id, job_id)
    if not item:
        raise DetachError("DETACH_NOT_FOUND", f"job '{job_id}' not found")
    stop_job(project_id, job_id, _grace(project_id), reason=reason)
    row = get_job(project_id, job_id)
    try:
        emit_detach_event(
            project_id,
            "detach_stopping_event",
            payload={
                "job_id": job_id,
                "agent_id": item.agent_id,
                "reason": str(reason or "manual"),
                "status": "stopping",
            },
            dedupe_key=f"detach_stopping:{job_id}",
        )
    except Exception:
        pass
    return {"ok": True, "project_id": project_id, "job": (row.to_dict() if row else None)}


def get_logs(project_id: str, job_id: str) -> dict:
    _project_cfg(project_id)
    row = get_job(project_id, job_id)
    if not row:
        raise DetachError("DETACH_NOT_FOUND", f"job '{job_id}' not found")
    tail = read_log_tail(project_id, job_id, _log_tail(project_id))
    return {"project_id": project_id, "job_id": job_id, "tail": tail}


def reconcile(project_id: str) -> dict:
    _project_cfg(project_id)
    jobs = list_jobs(project_id, limit=2000)
    now = time.time()

    # ttl enforcement
    ttl = _ttl(project_id)
    for item in jobs:
        if item.status != DetachStatus.RUNNING:
            continue
        started = item.started_at or item.created_at
        if (now - started) > ttl:
            stop_job(project_id, item.job_id, _grace(project_id), reason="ttl")

    # fifo cap enforcement per agent and per project
    jobs2 = list_jobs(project_id, limit=2000)
    agents = sorted({j.agent_id for j in jobs2})
    evicted = []
    for aid in agents:
        victims = select_fifo_victims(
            jobs2,
            max_running_project=_max_running_project(project_id),
            max_running_agent=_max_running_agent(project_id),
            agent_id=aid,
        )
        for v in victims:
            stop_job(project_id, v.job_id, _grace(project_id), reason="limit_fifo")
            evicted.append(v.job_id)
            jobs2 = [j for j in jobs2 if j.job_id != v.job_id]

    out = {"project_id": project_id, "evicted": evicted}
    try:
        emit_detach_event(
            project_id,
            "detach_reconciled_event",
            payload=out,
            dedupe_key=f"detach_reconcile:{int(now)}",
        )
    except Exception:
        pass
    return out


def startup_mark_lost(project_id: str) -> int:
    _project_cfg(project_id)
    n = mark_non_final_as_lost(project_id)
    if n > 0:
        try:
            emit_detach_event(
                project_id,
                "detach_lost_event",
                payload={"count": int(n), "reason": "startup_lost"},
                dedupe_key=f"detach_lost:{int(time.time())}",
            )
        except Exception:
            pass
    return n


def startup_mark_lost_all_projects() -> dict:
    rows = {}
    for pid in runtime_config.projects.keys():
        try:
            rows[pid] = startup_mark_lost(pid)
        except Exception:
            rows[pid] = 0
    return rows
