"""Detach background runner over docker exec."""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass

from gods.runtime.docker.manager import DockerRuntimeManager
from gods.runtime.docker.template import exec_args
from gods.runtime.detach.events import emit_detach_event
from gods.runtime.detach.models import DetachStatus
from gods.runtime.detach.store import append_log, transition_job, update_job


@dataclass
class _Handle:
    project_id: str
    job_id: str
    agent_id: str
    command: str
    stop_flag: threading.Event
    proc: subprocess.Popen | None = None
    thread: threading.Thread | None = None


_HANDLES: dict[str, _Handle] = {}
_LOCK = threading.Lock()


def _register(handle: _Handle):
    with _LOCK:
        _HANDLES[handle.job_id] = handle


def _unregister(job_id: str):
    with _LOCK:
        _HANDLES.pop(job_id, None)


def get_handle(job_id: str) -> _Handle | None:
    with _LOCK:
        return _HANDLES.get(job_id)


def _run_job(handle: _Handle, tail_chars: int):
    mgr = DockerRuntimeManager()
    try:
        mgr.ensure_agent_runtime(handle.project_id, handle.agent_id)
        spec = mgr.build_spec(handle.project_id, handle.agent_id)
        cmd = ["docker", *exec_args(spec, handle.command)]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        handle.proc = proc
        update_job(
            handle.project_id,
            handle.job_id,
            status=DetachStatus.RUNNING.value,
            started_at=time.time(),
            pid_or_container_exec_ref=str(proc.pid),
        )
        try:
            emit_detach_event(
                handle.project_id,
                "detach_started_event",
                payload={
                    "job_id": handle.job_id,
                    "agent_id": handle.agent_id,
                    "command": handle.command,
                    "pid_or_container_exec_ref": str(proc.pid),
                    "status": "running",
                },
                dedupe_key=f"detach_started:{handle.job_id}",
            )
        except Exception:
            pass

        if proc.stdout is not None:
            for line in proc.stdout:
                append_log(handle.project_id, handle.job_id, line, tail_chars)

        code = proc.wait()
        if handle.stop_flag.is_set():
            transition_job(handle.project_id, handle.job_id, DetachStatus.STOPPED, stop_reason="manual", exit_code=code)
            try:
                emit_detach_event(
                    handle.project_id,
                    "detach_stopped_event",
                    payload={
                        "job_id": handle.job_id,
                        "agent_id": handle.agent_id,
                        "exit_code": int(code),
                        "stop_reason": "manual",
                        "status": "stopped",
                    },
                    dedupe_key=f"detach_stopped:{handle.job_id}:{code}",
                )
            except Exception:
                pass
        elif code == 0:
            transition_job(handle.project_id, handle.job_id, DetachStatus.STOPPED, stop_reason="", exit_code=0)
            try:
                emit_detach_event(
                    handle.project_id,
                    "detach_stopped_event",
                    payload={
                        "job_id": handle.job_id,
                        "agent_id": handle.agent_id,
                        "exit_code": 0,
                        "stop_reason": "",
                        "status": "stopped",
                    },
                    dedupe_key=f"detach_stopped:{handle.job_id}:0",
                )
            except Exception:
                pass
        else:
            transition_job(handle.project_id, handle.job_id, DetachStatus.FAILED, stop_reason="error", exit_code=code)
            try:
                emit_detach_event(
                    handle.project_id,
                    "detach_failed_event",
                    payload={
                        "job_id": handle.job_id,
                        "agent_id": handle.agent_id,
                        "exit_code": int(code),
                        "stop_reason": "error",
                        "status": "failed",
                    },
                    dedupe_key=f"detach_failed:{handle.job_id}:{code}",
                )
            except Exception:
                pass
    except Exception as e:
        append_log(handle.project_id, handle.job_id, f"[runner-error] {e}\n", tail_chars)
        transition_job(handle.project_id, handle.job_id, DetachStatus.FAILED, stop_reason="error")
        try:
            emit_detach_event(
                handle.project_id,
                "detach_failed_event",
                payload={
                    "job_id": handle.job_id,
                    "agent_id": handle.agent_id,
                    "stop_reason": "error",
                    "status": "failed",
                    "error": str(e),
                },
                dedupe_key=f"detach_failed:{handle.job_id}:exception",
            )
        except Exception:
            pass
    finally:
        _unregister(handle.job_id)


def start_job(project_id: str, job_id: str, agent_id: str, command: str, tail_chars: int) -> bool:
    if get_handle(job_id):
        return False
    handle = _Handle(
        project_id=project_id,
        job_id=job_id,
        agent_id=agent_id,
        command=command,
        stop_flag=threading.Event(),
    )
    _register(handle)
    th = threading.Thread(target=_run_job, args=(handle, tail_chars), daemon=True)
    handle.thread = th
    th.start()
    return True


def stop_job(project_id: str, job_id: str, grace_sec: int, reason: str = "manual") -> bool:
    handle = get_handle(job_id)
    if not handle:
        # no live handle; mark stopped if possible
        transition_job(project_id, job_id, DetachStatus.STOPPED, stop_reason=reason)
        return False

    handle.stop_flag.set()
    transition_job(project_id, job_id, DetachStatus.STOPPING, stop_reason=reason)
    try:
        emit_detach_event(
            project_id,
            "detach_stopping_event",
            payload={"job_id": job_id, "reason": str(reason or "manual"), "status": "stopping"},
            dedupe_key=f"detach_stopping:{job_id}",
        )
    except Exception:
        pass

    proc = handle.proc
    if proc is None:
        transition_job(project_id, job_id, DetachStatus.STOPPED, stop_reason=reason)
        return True

    try:
        proc.terminate()
        deadline = time.time() + max(1, int(grace_sec))
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass
    return True
