"""Simulation scheduling service for server lifecycle (Angelia-backed)."""
from __future__ import annotations

import logging
from typing import Any

from gods.angelia.scheduler import angelia_supervisor
from gods.config import runtime_config
from gods.runtime.docker import DockerRuntimeManager

logger = logging.getLogger("GodsServer")


class SimulationService:
    def __init__(self):
        self._docker = DockerRuntimeManager()

    def pause_all_projects_on_startup(self) -> int:
        # Startup safety default: never auto-resume autonomous worlds after process restart.
        changed = 0
        for proj in runtime_config.projects.values():
            if proj.simulation_enabled:
                proj.simulation_enabled = False
                changed += 1
        if changed > 0:
            runtime_config.save()
        return changed

    def check_runtime_health(self):
        """Log docker availability when any project uses docker executor."""
        uses_docker = any(
            bool(getattr(p, "docker_enabled", True)) and str(getattr(p, "command_executor", "local")) == "docker"
            for p in runtime_config.projects.values()
        )
        if not uses_docker:
            return
        ok, msg = self._docker.docker_available()
        if ok:
            logger.info(f"Runtime health: Docker available ({msg})")
        else:
            logger.warning(f"Runtime health: Docker unavailable ({msg})")

    def start(self):
        angelia_supervisor.start()

    def stop(self):
        angelia_supervisor.stop()

    async def pulse_once(self) -> dict[str, Any]:
        # Compatibility shim for tests and manual checks.
        proj = runtime_config.projects.get(runtime_config.current_project)
        if not proj or (not proj.simulation_enabled) or (not proj.active_agents):
            return {"triggered": 0}

        project_id = runtime_config.current_project
        requires_docker = bool(getattr(proj, "docker_enabled", True)) and str(
            getattr(proj, "command_executor", "local")
        ) == "docker"
        if requires_docker:
            ok, msg = self._docker.docker_available()
            if not ok:
                proj.simulation_enabled = False
                runtime_config.save()
                logger.error(
                    "Simulation auto-stopped: project '%s' requires docker runtime but docker is unavailable (%s)",
                    project_id,
                    msg,
                )
                return {"triggered": 0, "error": f"docker_unavailable: {msg}", "project_id": project_id}

        emitted = angelia_supervisor.tick_timer_once(project_id).get("emitted", 0)
        return {"triggered": int(emitted)}


simulation_service = SimulationService()
