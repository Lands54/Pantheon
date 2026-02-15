"""Execution backend abstraction for run_command."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gods.config import runtime_config
from gods.runtime.docker import DockerRuntimeManager
from gods.runtime.docker.models import CommandExecutionResult

try:
    import resource
except Exception:  # pragma: no cover
    resource = None


@dataclass
class ExecutionLimits:
    timeout_sec: int
    max_memory_mb: int
    max_cpu_sec: int


class ExecutionBackend:
    def ensure_agent_runtime(self, project_id: str, agent_id: str):
        return None

    def execute(
        self,
        *,
        command_parts: list[str],
        command_text: str,
        territory: Path,
        project_id: str,
        agent_id: str,
        limits: ExecutionLimits,
    ) -> CommandExecutionResult:
        raise NotImplementedError

    def cleanup_agent_runtime(self, project_id: str, agent_id: str):
        return None


class LocalSubprocessBackend(ExecutionBackend):
    @staticmethod
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

    def execute(
        self,
        *,
        command_parts: list[str],
        command_text: str,
        territory: Path,
        project_id: str,
        agent_id: str,
        limits: ExecutionLimits,
    ) -> CommandExecutionResult:
        _ = command_text, project_id, agent_id
        try:
            proc = subprocess.run(
                command_parts,
                cwd=territory,
                capture_output=True,
                text=True,
                timeout=max(1, int(limits.timeout_sec)),
                preexec_fn=self._build_preexec_fn(limits.max_memory_mb, limits.max_cpu_sec),
            )
            return CommandExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
            )
        except subprocess.TimeoutExpired as e:
            return CommandExecutionResult(
                exit_code=None,
                stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
                stderr=(e.stderr or "") if isinstance(e.stderr, str) else "",
                error_code="LOCAL_TIMEOUT",
                error_message=f"Command timed out after {limits.timeout_sec}s.",
                timed_out=True,
            )
        except Exception as e:
            return CommandExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                error_code="LOCAL_EXEC_FAILED",
                error_message=str(e),
            )


class DockerBackend(ExecutionBackend):
    def __init__(self):
        self.manager = DockerRuntimeManager()

    def ensure_agent_runtime(self, project_id: str, agent_id: str):
        return self.manager.ensure_agent_runtime(project_id, agent_id)

    def execute(
        self,
        *,
        command_parts: list[str],
        command_text: str,
        territory: Path,
        project_id: str,
        agent_id: str,
        limits: ExecutionLimits,
    ) -> CommandExecutionResult:
        _ = command_parts, territory
        return self.manager.execute(
            project_id=project_id,
            agent_id=agent_id,
            command=command_text,
            timeout_sec=limits.timeout_sec,
        )

    def cleanup_agent_runtime(self, project_id: str, agent_id: str):
        self.manager.stop_agent_runtime(project_id, agent_id)


def resolve_execution_backend(project_id: str) -> ExecutionBackend:
    proj = runtime_config.projects.get(project_id)
    executor = str(getattr(proj, "command_executor", "local") if proj else "local").strip().lower()
    docker_enabled = bool(getattr(proj, "docker_enabled", True) if proj else True)
    if executor == "docker" and docker_enabled:
        return DockerBackend()
    return LocalSubprocessBackend()
