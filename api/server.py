"""
Gods Platform - FastAPI Server (Refactored)
Main server entry point with modularized routes.
"""
import asyncio
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from gods.config import runtime_config
from api.routes import config, projects, agents, communication, tool_gateway
from api.scheduler import pick_pulse_batch, pulse_agent_sync

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GodsServer")

app = FastAPI(title="Gods Platform API", version="2.0.0")

# Register routers
app.include_router(config.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(communication.router)
app.include_router(tool_gateway.router)
if runtime_config.enable_legacy_social_api:
    from api.routes import legacy_social
    app.include_router(legacy_social.router)
    logger.info("Legacy social API routes enabled (/broadcast, /prayers/check).")


# --- Simulation Heartbeat ---
def pause_all_projects_on_startup() -> int:
    """
    Enforce safety policy: server startup never auto-resumes simulations.
    Returns number of projects switched from enabled to disabled.
    """
    changed = 0
    for proj in runtime_config.projects.values():
        if proj.simulation_enabled:
            proj.simulation_enabled = False
            changed += 1
    if changed > 0:
        runtime_config.save()
    return changed



async def simulation_loop():
    """
    Event-driven autonomous loop:
    - pulse idle agents only
    - prioritize inbox-driven wakeups
    - heartbeat is fallback for silent periods
    """

    logger.info("Universal Simulation Heartbeat initiated.")
    while True:
        proj = runtime_config.projects.get(runtime_config.current_project)
        if proj and proj.simulation_enabled and proj.active_agents:
            project_id = runtime_config.current_project
            active_agents = list(proj.active_agents)
            batch_size = max(1, int(getattr(proj, "autonomous_batch_size", 4)))
            batch = pick_pulse_batch(project_id, active_agents, batch_size)
            if batch:
                logger.info(f"✨ Event Pulse: {len(batch)} agents in {project_id}")
                tasks = [
                    asyncio.to_thread(pulse_agent_sync, project_id, agent_id, reason, False)
                    for agent_id, reason in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        # Fast polling for event-driven wakeups without 1s alarm spam to each agent.
        await asyncio.sleep(1.0)


@app.on_event("startup")
async def startup_event():
    """Initialize simulation on startup."""
    changed = pause_all_projects_on_startup()
    if changed > 0:
        logger.info("Startup safety: paused all projects (simulation_enabled=false).")
    asyncio.create_task(simulation_loop())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "operational", "version": "2.0.1-REAL-RESTART"}


# Serve frontend
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
