"""
Gods Tools - Execution Module
Command execution with scoped capabilities and runtime safeguards.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse

from langchain.tools import tool

from gods.config import runtime_config
from .filesystem import validate_path

try:
    import resource
except Exception:  # pragma: no cover
    resource = None


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
        return "Divine Restriction: Empty incantation."

    executable = parts[0]
    base = Path(executable).name.lower()

    if _is_venv_binary(executable, territory):
        # .venv/bin/python|pip|uv are always allowed within territory.
        pass
    elif base in {"pip", "pip3"}:
        return "Divine Restriction: Use a project virtualenv executable like .venv/bin/pip."
    elif base not in SAFE_BASE_COMMANDS:
        return f"Divine Restriction: Command '{base}' is outside your authorized capabilities."

    if base == "curl":
        urls = [p for p in parts[1:] if p.startswith("http://") or p.startswith("https://")]
        if not urls:
            return "Divine Restriction: curl requires an explicit localhost URL."
        for url in urls:
            if not _is_localhost_url(url):
                return f"Divine Restriction: Network access is limited to localhost. Rejected: {url}"

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


def _build_preexec_fn(max_memory_mb: int, max_cpu_sec: int):
    if resource is None or os.name == "nt":
        return None

    def _limit():
        mem_bytes = max_memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_sec, max_cpu_sec))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        except Exception:
            pass

    return _limit


@tool
def run_command(command: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Run an approved command within your project territory, with resource and concurrency limits."""
    if _has_forbidden_shell_syntax(command):
        return "Divine Restriction: Complex shell chaining is forbidden."

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return f"Divine Restriction: Invalid command syntax ({e})."

    try:
        territory = validate_path(caller_id, project_id, ".")
    except Exception as e:
        return f"Divine Restriction: {str(e)}"

    validation_error = _validate_command(parts, territory)
    if validation_error:
        return validation_error

    max_parallel, timeout_sec, max_memory_mb, max_cpu_sec = _get_project_limits(project_id)
    output_limit = _get_output_limit(project_id)
    project_sem = _get_project_semaphore(project_id, max_parallel)
    agent_lock = _get_agent_lock(project_id, caller_id)

    if not agent_lock.acquire(blocking=False):
        return "Divine Restriction: You already have a running command. Wait for it to finish."
    if not project_sem.acquire(blocking=False):
        agent_lock.release()
        return "Divine Restriction: Project command queue is full. Retry shortly."

    try:
        result = subprocess.run(
            parts,
            cwd=territory,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            preexec_fn=_build_preexec_fn(max_memory_mb, max_cpu_sec),
        )
        stdout = (result.stdout or "")[:output_limit]
        stderr = (result.stderr or "")[:output_limit]
        return (
            f"Manifestation Result (exit={result.returncode}):\n"
            f"STDOUT: {stdout}\n"
            f"STDERR: {stderr}"
        )
    except subprocess.TimeoutExpired:
        return f"Manifestation Failed: Command timed out after {timeout_sec}s."
    except Exception as e:
        return f"Manifestation Failed: {str(e)}"
    finally:
        project_sem.release()
        agent_lock.release()
