"""
Gods Tools - Execution Module
Command execution with scoped capabilities and runtime safeguards.
"""
from __future__ import annotations

import shlex
import threading
from pathlib import Path
from urllib.parse import urlparse

from langchain_core.tools import tool

from gods.config import runtime_config
from gods.runtime.execution_backend import ExecutionLimits, resolve_execution_backend
from .filesystem import validate_path


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
PROJECT_GUARD_LOCK = threading.Lock()
PROJECT_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}
AGENT_LOCKS: dict[tuple[str, str], threading.Lock] = {}


def _format_exec_error(territory: Path | None, title: str, reason: str, suggestion: str) -> str:
    cwd = territory if territory is not None else "unknown"
    return (
        f"[Current CWD: {cwd}] "
        f"{title}: {reason}\n"
        f"Suggested next step: {suggestion}"
    )


def _has_forbidden_shell_syntax(command: str) -> bool:
    return any(char in command for char in [";", "&", "|", ">", "<", "`", "$"])


def _is_path_within(base_dir: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base_dir)
        return True
    except ValueError:
        return False


def _resolve_exec_path(exec_part: str, territory: Path) -> Path:
    raw = Path(exec_part)
    return raw.resolve() if raw.is_absolute() else (territory / raw).resolve()


def _is_venv_binary(exec_part: str, territory: Path) -> bool:
    resolved = _resolve_exec_path(exec_part, territory)
    if not _is_path_within(territory, resolved):
        return False
    # expected: <territory>/.venv/bin/python OR pip (also supports venv/)
    parent = resolved.parent
    if parent.name != "bin":
        return False
    venv_dir = parent.parent.name
    if venv_dir not in {".venv", "venv"}:
        return False
    return resolved.name in {"python", "python3", "pip", "pip3", "uv"}


def _is_localhost_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in LOCALHOST_NAMES


def _validate_command(parts: list[str], territory: Path) -> str | None:
    if not parts:
        return _format_exec_error(
            territory,
            "Command Error",
            "Empty incantation.",
            "Provide a concrete command, for example: 'python app.py' or 'ls'.",
        )

    executable = parts[0]
    base = Path(executable).name.lower()

    if _is_venv_binary(executable, territory):
        # .venv/bin/python|pip|uv are always allowed within territory.
        pass
    elif base in {"pip", "pip3"}:
        return _format_exec_error(
            territory,
            "Divine Restriction",
            "Plain pip is blocked to avoid polluting global environment.",
            "Use a project virtualenv executable like '.venv/bin/pip ...' inside your territory.",
        )
    elif base not in SAFE_BASE_COMMANDS:
        return _format_exec_error(
            territory,
            "Divine Restriction",
            f"Command '{base}' is outside your authorized capabilities.",
            f"Use one of the approved commands or .venv/bin/python/.venv/bin/pip. Requested: '{base}'.",
        )

    if base == "curl":
        urls = [p for p in parts[1:] if p.startswith("http://") or p.startswith("https://")]
        if not urls:
            return _format_exec_error(
                territory,
                "Command Error",
                "curl requires an explicit localhost URL.",
                "Example: curl http://localhost:8000/health",
            )
        for url in urls:
            if not _is_localhost_url(url):
                return _format_exec_error(
                    territory,
                    "Divine Restriction",
                    f"Network access is limited to localhost. Rejected: {url}",
                    "Use localhost/127.0.0.1 endpoints only.",
                )

    return None


def _get_project_limits(project_id: str) -> tuple[int, int, int, int]:
    proj = runtime_config.projects.get(project_id)
    max_parallel = max(1, int(getattr(proj, "command_max_parallel", 2) if proj else 2))
    timeout_sec = max(1, int(getattr(proj, "command_timeout_sec", 60) if proj else 60))
    max_memory_mb = max(128, int(getattr(proj, "command_max_memory_mb", 512) if proj else 512))
    max_cpu_sec = max(1, int(getattr(proj, "command_max_cpu_sec", 15) if proj else 15))
    return max_parallel, timeout_sec, max_memory_mb, max_cpu_sec


def _get_output_limit(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    return max(512, int(getattr(proj, "command_max_output_chars", 4000) if proj else 4000))


def _get_project_semaphore(project_id: str, max_parallel: int) -> threading.BoundedSemaphore:
    with PROJECT_GUARD_LOCK:
        sem = PROJECT_SEMAPHORES.get(project_id)
        if sem is None:
            sem = threading.BoundedSemaphore(value=max_parallel)
            PROJECT_SEMAPHORES[project_id] = sem
        return sem


def _get_agent_lock(project_id: str, caller_id: str) -> threading.Lock:
    key = (project_id, caller_id)
    with PROJECT_GUARD_LOCK:
        lock = AGENT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            AGENT_LOCKS[key] = lock
        return lock


@tool
def run_command(command: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Run an approved command within your project territory, with resource and concurrency limits."""
    if _has_forbidden_shell_syntax(command):
        return _format_exec_error(
            None,
            "Divine Restriction",
            "Complex shell chaining is forbidden.",
            "Run one command per invocation; avoid ; & | > < ` $.",
        )

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return _format_exec_error(
            None,
            "Command Error",
            f"Invalid command syntax ({e}).",
            "Check quotes and escaping, then retry.",
        )

    try:
        territory = validate_path(caller_id, project_id, ".")
    except Exception as e:
        return _format_exec_error(
            None,
            "Territory Error",
            str(e),
            "Use a valid caller_id/project_id and retry.",
        )

    validation_error = _validate_command(parts, territory)
    if validation_error:
        return validation_error

    max_parallel, timeout_sec, max_memory_mb, max_cpu_sec = _get_project_limits(project_id)
    output_limit = _get_output_limit(project_id)
    project_sem = _get_project_semaphore(project_id, max_parallel)
    agent_lock = _get_agent_lock(project_id, caller_id)

    if not agent_lock.acquire(blocking=False):
        return _format_exec_error(
            territory,
            "Concurrency Limit",
            "You already have a running command.",
            "Wait for it to finish before launching another one.",
        )
    if not project_sem.acquire(blocking=False):
        agent_lock.release()
        return _format_exec_error(
            territory,
            "Concurrency Limit",
            "Project command queue is full.",
            "Retry shortly or reduce parallel command usage.",
        )

    try:
        backend = resolve_execution_backend(project_id)
        result = backend.execute(
            command_parts=parts,
            command_text=command,
            territory=territory,
            project_id=project_id,
            agent_id=caller_id,
            limits=ExecutionLimits(
                timeout_sec=timeout_sec,
                max_memory_mb=max_memory_mb,
                max_cpu_sec=max_cpu_sec,
            ),
        )
        if result.error_code:
            if result.timed_out or result.error_code in {"LOCAL_TIMEOUT", "DOCKER_TIMEOUT"}:
                return _format_exec_error(
                    territory,
                    "Execution Timeout",
                    result.error_message or f"Command timed out after {timeout_sec}s.",
                    "Break the task into smaller steps or increase command_timeout_sec via config.",
                )
            code = result.error_code
            msg = result.error_message or "unknown execution backend error"
            if code in {"DOCKER_NOT_AVAILABLE", "DOCKER_COMMAND_FAILED"}:
                return _format_exec_error(
                    territory,
                    "Execution Backend Error",
                    f"{code}: {msg}",
                    "Install/start Docker or set config command_executor=local.",
                )
            return _format_exec_error(
                territory,
                "Execution Failed",
                f"{code}: {msg}",
                "Check command arguments and local environment, then retry.",
            )

        stdout = (result.stdout or "")[:output_limit]
        stderr = (result.stderr or "")[:output_limit]
        return (
            f"Manifestation Result (exit={result.exit_code}):\n"
            f"STDOUT: {stdout}\n"
            f"STDERR: {stderr}"
        )
    except Exception as e:
        return _format_exec_error(
            territory,
            "Execution Failed",
            str(e),
            "Check command arguments and local environment, then retry.",
        )
    finally:
        project_sem.release()
        agent_lock.release()
