"""
Gods Platform - FastAPI App Composition Root
Only app assembly lives here.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import agents, angelia, communication, config, events, hermes, mnemosyne, projects, tool_gateway
from api.services import simulation_service
from gods.config import runtime_config
from gods.events.migrate import migrate_all_projects
from gods.mnemosyne import ensure_memory_policy, validate_memory_policy
from gods.runtime.detach import startup_mark_lost_all_projects

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GodsServer")

app = FastAPI(title="Gods Platform API", version="2.0.0")

app.include_router(config.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(communication.router)
app.include_router(tool_gateway.router)
app.include_router(hermes.router)
app.include_router(mnemosyne.router)
app.include_router(angelia.router)
app.include_router(events.router)


@app.on_event("startup")
async def startup_event():
    # Safety-first startup: pause worlds first, then start scheduler loop.
    changed = simulation_service.pause_all_projects_on_startup()
    migr = migrate_all_projects()
    lost = startup_mark_lost_all_projects()
    for pid in runtime_config.projects.keys():
        try:
            ensure_memory_policy(pid)
            validate_memory_policy(pid, ensure_exists=True)
        except Exception as e:
            logger.error(f"Startup validation failed for project '{pid}': {e}")
            raise
    logger.info(f"Event-bus migration summary: {migr}")
    logger.info(f"Detach startup reconcile: marked lost jobs per project: {lost}")
    simulation_service.check_runtime_health()
    if changed > 0:
        logger.info("Startup safety: paused all projects (simulation_enabled=false).")
    simulation_service.start()


@app.on_event("shutdown")
async def shutdown_event():
    simulation_service.stop()


@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "2.0.1-REAL-RESTART"}


frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
