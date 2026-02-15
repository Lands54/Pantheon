"""Docker container lifecycle manager for per-agent runtime."""
from __future__ import annotations

import json
from typing import Iterable

from gods.config import runtime_config
from gods.runtime.docker.exec import require_ok, run_docker
from gods.runtime.docker.models import AgentRuntimeSpec, ContainerStatus
from gods.runtime.docker.paths import agent_territory, container_name, project_container_prefix, repo_root
from gods.runtime.docker.template import create_args, exec_args


class DockerRuntimeManager:
    """Manage long-lived docker containers for agent runtimes."""

    def docker_available(self) -> tuple[bool, str]:
        res = run_docker(["version", "--format", "{{.Server.Version}}"], timeout_sec=8)
        if res.error_code:
            return False, res.error_message
        if (res.exit_code or 0) != 0:
            msg = (res.stderr or res.stdout or "docker unavailable").strip()
            return False, msg
        return True, (res.stdout or "").strip()

    def build_spec(self, project_id: str, agent_id: str) -> AgentRuntimeSpec:
        proj = runtime_config.projects.get(project_id)
        image = str(getattr(proj, "docker_image", "gods-agent-base:py311") if proj else "gods-agent-base:py311")
        net = str(getattr(proj, "docker_network_mode", "bridge_local_only") if proj else "bridge_local_only")
        readonly = bool(getattr(proj, "docker_readonly_rootfs", False) if proj else False)
        extra_env = dict(getattr(proj, "docker_extra_env", {}) if proj else {})
        cpu = float(getattr(proj, "docker_cpu_limit", 1.0) if proj else 1.0)
        mem = int(getattr(proj, "docker_memory_limit_mb", 512) if proj else 512)
        return AgentRuntimeSpec(
            project_id=project_id,
            agent_id=agent_id,
            container_name=container_name(project_id, agent_id),
            image=image,
            host_agent_dir=agent_territory(project_id, agent_id),
            host_repo_dir=repo_root() / "gods",
            network_mode=net,
            readonly_rootfs=readonly,
            extra_env=extra_env,
            cpu_limit=cpu,
            memory_limit_mb=mem,
        )

    def _inspect(self, cname: str) -> dict | None:
        res = run_docker(["inspect", cname], timeout_sec=8)
        if res.error_code:
            return None
        if (res.exit_code or 0) != 0:
            return None
        try:
            arr = json.loads(res.stdout or "[]")
            if isinstance(arr, list) and arr:
                return arr[0]
        except Exception:
            return None
        return None

    def get_agent_status(self, project_id: str, agent_id: str) -> ContainerStatus:
        spec = self.build_spec(project_id, agent_id)
        info = self._inspect(spec.container_name)
        if not info:
            return ContainerStatus(
                project_id=project_id,
                agent_id=agent_id,
                container_name=spec.container_name,
                exists=False,
                running=False,
                image=spec.image,
                status_text="not_found",
            )
        state = info.get("State") or {}
        config = info.get("Config") or {}
        running = bool(state.get("Running", False))
        return ContainerStatus(
            project_id=project_id,
            agent_id=agent_id,
            container_name=spec.container_name,
            exists=True,
            running=running,
            image=str(config.get("Image", spec.image)),
            status_text=str(state.get("Status", "unknown")),
            container_id=str(info.get("Id", ""))[:12],
        )

    def ensure_agent_runtime(self, project_id: str, agent_id: str):
        spec = self.build_spec(project_id, agent_id)
        spec.host_agent_dir.mkdir(parents=True, exist_ok=True)
        st = self.get_agent_status(project_id, agent_id)
        if st.exists and st.running:
            return st
        if st.exists and (not st.running):
            res = run_docker(["start", spec.container_name], timeout_sec=20)
            require_ok(res)
            return self.get_agent_status(project_id, agent_id)

        create = run_docker(create_args(spec), timeout_sec=60)
        require_ok(create)
        return self.get_agent_status(project_id, agent_id)

    def restart_agent_runtime(self, project_id: str, agent_id: str) -> ContainerStatus:
        spec = self.build_spec(project_id, agent_id)
        st = self.get_agent_status(project_id, agent_id)
        if not st.exists:
            return self.ensure_agent_runtime(project_id, agent_id)
        res = run_docker(["restart", spec.container_name], timeout_sec=30)
        require_ok(res)
        return self.get_agent_status(project_id, agent_id)

    def execute(self, project_id: str, agent_id: str, command: str, timeout_sec: int):
        st = self.ensure_agent_runtime(project_id, agent_id)
        spec = self.build_spec(project_id, agent_id)
        _ = st
        return run_docker(exec_args(spec, command), timeout_sec=timeout_sec)

    def stop_agent_runtime(self, project_id: str, agent_id: str):
        spec = self.build_spec(project_id, agent_id)
        st = self.get_agent_status(project_id, agent_id)
        if not st.exists:
            return
        run_docker(["stop", spec.container_name], timeout_sec=20)

    def list_project_runtimes(self, project_id: str, agent_ids: Iterable[str]) -> list[dict]:
        rows = []
        for aid in agent_ids:
            st = self.get_agent_status(project_id, aid)
            rows.append(
                {
                    "project_id": st.project_id,
                    "agent_id": st.agent_id,
                    "container_name": st.container_name,
                    "exists": st.exists,
                    "running": st.running,
                    "image": st.image,
                    "status": st.status_text,
                    "container_id": st.container_id,
                }
            )
        return rows

    def reconcile_project(self, project_id: str, active_agents: Iterable[str]) -> dict:
        active = set(active_agents)
        ensured = []
        stopped = []
        prefix = project_container_prefix(project_id)

        for aid in sorted(active):
            st = self.ensure_agent_runtime(project_id, aid)
            ensured.append({"agent_id": aid, "running": st.running, "exists": st.exists})

        ps = run_docker(["ps", "-a", "--format", "{{.Names}}"], timeout_sec=10)
        names = []
        if not ps.error_code and (ps.exit_code or 0) == 0:
            names = [line.strip() for line in (ps.stdout or "").splitlines() if line.strip()]
        for name in names:
            if not name.startswith(prefix):
                continue
            agent_part = name[len(prefix) :]
            if agent_part in active:
                continue
            run_docker(["stop", name], timeout_sec=20)
            stopped.append(name)

        return {"project_id": project_id, "ensured": ensured, "stopped": stopped}

    def stop_project(self, project_id: str, active_agents: Iterable[str]):
        for aid in active_agents:
            self.stop_agent_runtime(project_id, aid)
