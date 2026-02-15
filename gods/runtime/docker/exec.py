"""Low-level docker command execution helpers."""
from __future__ import annotations

import subprocess

from gods.runtime.docker.errors import DOCKER_COMMAND_FAILED, DOCKER_NOT_AVAILABLE, DOCKER_TIMEOUT, DockerRuntimeError
from gods.runtime.docker.models import CommandExecutionResult


def run_docker(args: list[str], timeout_sec: int = 30) -> CommandExecutionResult:
    cmd = ["docker", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
        )
        return CommandExecutionResult(
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except FileNotFoundError as e:
        return CommandExecutionResult(
            exit_code=None,
            stdout="",
            stderr="",
            error_code=DOCKER_NOT_AVAILABLE,
            error_message=str(e),
        )
    except subprocess.TimeoutExpired as e:
        return CommandExecutionResult(
            exit_code=None,
            stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
            stderr=(e.stderr or "") if isinstance(e.stderr, str) else "",
            error_code=DOCKER_TIMEOUT,
            error_message=f"docker command timed out after {timeout_sec}s",
            timed_out=True,
        )
    except Exception as e:
        return CommandExecutionResult(
            exit_code=None,
            stdout="",
            stderr="",
            error_code=DOCKER_COMMAND_FAILED,
            error_message=str(e),
        )


def require_ok(result: CommandExecutionResult, code: str = DOCKER_COMMAND_FAILED):
    if result.error_code:
        raise DockerRuntimeError(result.error_code, result.error_message or "docker command failed")
    if (result.exit_code or 0) != 0:
        raise DockerRuntimeError(code, (result.stderr or result.stdout or "docker command failed").strip())
