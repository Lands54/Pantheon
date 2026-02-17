"""Simulation scheduling service for server lifecycle (Angelia-backed)."""
from __future__ import annotations

import logging

from gods.angelia import facade as angelia_facade
from gods.config import runtime_config
from gods.runtime import facade as runtime_facade

logger = logging.getLogger("GodsServer")


class SimulationService:
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
        ok, msg = runtime_facade.docker_available()
        if ok:
            logger.info(f"Runtime health: Docker available ({msg})")
        else:
            logger.warning(f"Runtime health: Docker unavailable ({msg})")

    def start(self):
        angelia_facade.start_supervisor()

    def stop(self):
        angelia_facade.stop_supervisor()


simulation_service = SimulationService()
