"""Data models for docker runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DockerRuntimeSettings:
    project_id: str
    image: str
    network_mode: str
    readonly_rootfs: bool
    extra_env: dict[str, str] = field(default_factory=dict)
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512


@dataclass
class AgentRuntimeSpec:
    project_id: str
    agent_id: str
    container_name: str
    image: str
    host_agent_dir: Path
    host_repo_dir: Path
    container_agent_dir: str = "/workspace/agent"
    container_repo_dir: str = "/workspace/repo"
    network_mode: str = "bridge_local_only"
    readonly_rootfs: bool = False
    extra_env: dict[str, str] = field(default_factory=dict)
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512


@dataclass
class ContainerStatus:
    project_id: str
    agent_id: str
    container_name: str
    exists: bool
    running: bool
    image: str
    status_text: str = ""
    container_id: str = ""


@dataclass
class CommandExecutionResult:
    exit_code: int | None
    stdout: str
    stderr: str
    error_code: str = ""
    error_message: str = ""
    timed_out: bool = False
