"""Simulation scheduling service for server lifecycle."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from api.scheduler import pick_pulse_batch, pulse_agent_sync
from gods.config import runtime_config

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

    async def pulse_once(self) -> dict[str, Any]:
        proj = runtime_config.projects.get(runtime_config.current_project)
        if not proj or (not proj.simulation_enabled) or (not proj.active_agents):
            return {"triggered": 0}

        project_id = runtime_config.current_project
        active_agents = list(proj.active_agents)
        batch_size = max(1, int(getattr(proj, "autonomous_batch_size", 4)))
        # Scheduler prioritizes inbox-driven agents before heartbeat candidates.
        batch = pick_pulse_batch(project_id, active_agents, batch_size)
        if not batch:
            return {"triggered": 0}

        logger.info(f"✨ Event Pulse: {len(batch)} agents in {project_id}")
        tasks = [
            asyncio.to_thread(pulse_agent_sync, project_id, agent_id, reason, False)
            for agent_id, reason in batch
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        return {"triggered": len(batch)}

    async def simulation_loop(self, poll_interval_sec: float = 1.0):
        logger.info("Universal Simulation Heartbeat initiated.")
        while True:
            await self.pulse_once()
            await asyncio.sleep(poll_interval_sec)


simulation_service = SimulationService()
