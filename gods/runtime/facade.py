"""Public facade for runtime domain operations."""
from __future__ import annotations

from gods.runtime.detach import (
    DetachJob,
    DetachError,
    DetachStatus,
    get_logs as detach_get_logs,
    list_for_api as detach_list_for_api,
    reconcile as detach_reconcile,
    startup_mark_lost as detach_startup_mark_lost,
    startup_mark_lost_all_projects,
    stop as detach_stop,
    submit as detach_submit,
)
from gods.runtime.detach.policy import select_fifo_victims
from gods.runtime.detach.store import (
    append_log,
    create_job,
    get_job,
    mark_non_final_as_lost,
    read_log_tail,
    transition_job,
    update_job,
)
from gods.runtime.execution_backend import DockerBackend, LocalSubprocessBackend, resolve_execution_backend
from gods.runtime.docker import DockerRuntimeManager
from gods.runtime.docker.template import create_args as create_docker_args

_docker = DockerRuntimeManager()


def docker_available():
    return _docker.docker_available()


def ensure_agent_runtime(project_id: str, agent_id: str):
    return _docker.ensure_agent_runtime(project_id, agent_id)


def stop_agent_runtime(project_id: str, agent_id: str):
    return _docker.stop_agent_runtime(project_id, agent_id)


def restart_agent_runtime(project_id: str, agent_id: str):
    return _docker.restart_agent_runtime(project_id, agent_id)


def list_project_runtimes(project_id: str, active_agents: list[str]):
    return _docker.list_project_runtimes(project_id, active_agents)


def reconcile_project(project_id: str, active_agents: list[str]):
    return _docker.reconcile_project(project_id, active_agents)


__all__ = [
    "DetachError",
    "DetachJob",
    "DetachStatus",
    "DockerBackend",
    "LocalSubprocessBackend",
    "resolve_execution_backend",
    "detach_submit",
    "detach_list_for_api",
    "detach_stop",
    "detach_reconcile",
    "detach_get_logs",
    "detach_startup_mark_lost",
    "startup_mark_lost_all_projects",
    "create_job",
    "get_job",
    "update_job",
    "transition_job",
    "mark_non_final_as_lost",
    "append_log",
    "read_log_tail",
    "select_fifo_victims",
    "DockerRuntimeManager",
    "create_docker_args",
    "docker_available",
    "ensure_agent_runtime",
    "stop_agent_runtime",
    "restart_agent_runtime",
    "list_project_runtimes",
    "reconcile_project",
]
