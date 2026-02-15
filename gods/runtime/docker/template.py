"""Docker runtime template builders."""
from __future__ import annotations

from gods.runtime.docker.models import AgentRuntimeSpec


def _network_args(network_mode: str) -> list[str]:
    # Phase-1 keeps bridge networking. Fine-grained egress control can be hardened later.
    if network_mode == "bridge_local_only":
        return ["--network", "bridge"]
    if network_mode == "none":
        return ["--network", "none"]
    return ["--network", "bridge"]


def create_args(spec: AgentRuntimeSpec) -> list[str]:
    args = [
        "run",
        "-d",
        "--name",
        spec.container_name,
        "--workdir",
        spec.container_agent_dir,
        "--cpus",
        str(max(0.1, float(spec.cpu_limit))),
        "--memory",
        f"{max(128, int(spec.memory_limit_mb))}m",
        "-v",
        f"{spec.host_agent_dir.resolve()}:{spec.container_agent_dir}:rw",
        "-v",
        f"{spec.host_repo_dir.resolve()}:{spec.container_repo_dir}/gods:ro",
        "-e",
        f"PYTHONPATH={spec.container_repo_dir}",
        "-e",
        f"GODS_PROJECT_ID={spec.project_id}",
        "-e",
        f"GODS_AGENT_ID={spec.agent_id}",
    ]
    if spec.readonly_rootfs:
        args.append("--read-only")
    args.extend(_network_args(spec.network_mode))
    for k, v in (spec.extra_env or {}).items():
        args.extend(["-e", f"{k}={v}"])
    args.extend([spec.image, "tail", "-f", "/dev/null"])
    return args


def exec_args(spec: AgentRuntimeSpec, command: str) -> list[str]:
    return [
        "exec",
        "-i",
        "-w",
        spec.container_agent_dir,
        "-e",
        f"PYTHONPATH={spec.container_repo_dir}",
        spec.container_name,
        "sh",
        "-lc",
        command,
    ]
