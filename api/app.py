"""
Gods Platform - FastAPI App Composition Root
Only app assembly lives here.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import agents, communication, config, hermes, mnemosyne, projects, tool_gateway
from api.services import simulation_service
from gods.config import runtime_config

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
if runtime_config.enable_legacy_social_api:
    from api.routes import legacy_social

    app.include_router(legacy_social.router)
    logger.info("Legacy social API routes enabled (/broadcast, /prayers/check).")


@app.on_event("startup")
async def startup_event():
    # Safety-first startup: pause worlds first, then start scheduler loop.
    changed = simulation_service.pause_all_projects_on_startup()
    if changed > 0:
        logger.info("Startup safety: paused all projects (simulation_enabled=false).")
    asyncio.create_task(simulation_service.simulation_loop())


@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "2.0.1-REAL-RESTART"}


frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
