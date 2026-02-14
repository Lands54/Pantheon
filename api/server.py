"""
Gods Platform - FastAPI Server (Refactored)
Main server entry point with modularized routes.
"""
import asyncio
import logging
import random
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from gods.config import runtime_config
from api.routes import config, projects, agents, communication

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GodsServer")

app = FastAPI(title="Gods Platform API", version="2.0.0")

# Register routers
app.include_router(config.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(communication.router)


# --- Simulation Heartbeat ---

async def simulation_loop():
    """Background loop that randomly triggers agent pulses."""
    from gods.agents.base import GodAgent
    from langchain_core.messages import HumanMessage
    
    logger.info("Universal Simulation Heartbeat initiated.")
    while True:
        proj = runtime_config.projects.get(runtime_config.current_project)
        if proj and proj.simulation_enabled and proj.active_agents:
            # Pick a lucky agent
            agent_id = random.choice(proj.active_agents)
            logger.info(f"✨ Simulation Pulse: Awakening {agent_id}")
            
            try:
                # Trigger autonomous pulse
                agent = GodAgent(agent_id=agent_id, project_id=runtime_config.current_project)
                state = {
                    "project_id": runtime_config.current_project,
                    "messages": [HumanMessage(content="EXISTENCE_PULSE: Update your state and personal chronicles.", name="system")],
                    "context": "Autonomous evolution pulse",
                    "next_step": ""
                }
                agent.process(state)
            except Exception as e:
                logger.error(f"Pulse failed for {agent_id}: {e}")
        
        # Sleep for a random interval within configured bounds
        interval = random.randint(proj.simulation_interval_min if proj else 10, proj.simulation_interval_max if proj else 40)
        await asyncio.sleep(interval)


@app.on_event("startup")
async def startup_event():
    """Initialize simulation on startup."""
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
