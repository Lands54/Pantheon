"""
Gods Platform - FastAPI Server (Persistent & Dynamic)
"""
import asyncio
import json
import logging
import os
import shutil
from typing import AsyncGenerator, List, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from gods_platform.workflow import create_gods_workflow, create_private_workflow
from gods_platform.config import runtime_config, get_available_agents, AgentModelConfig
from platform_logic.agents import GodAgent
from langchain_core.messages import HumanMessage, AIMessage
from concurrent.futures import ThreadPoolExecutor

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GodsServer")

app = FastAPI(title="Gods Platform API")

# Serve UI from /static
# In production, this would be the frontend/dist folder
if Path("frontend/dist").exists():
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
else:
    # Fallback to old web if exists
    if Path("web").exists():
        app.mount("/old", StaticFiles(directory="web"), name="old")

@app.get("/health")
async def health():
    return {"status": "Gods Server is Active", "agents": get_available_agents()}

executor = ThreadPoolExecutor(max_workers=20)

# --- Models ---

class OracleRequest(BaseModel):
    task: str
    thread_id: str = "temple_main"

class PrivateChatRequest(BaseModel):
    agent_id: str
    message: str
    thread_id: str = "private_session"

class UpdateConfigRequest(BaseModel):
    openrouter_api_key: str
    agent_settings: Dict[str, AgentModelConfig]
    active_agents: List[str]

class CreateAgentRequest(BaseModel):
    agent_id: str
    directives: str

# --- Config & Agent Management ---

@app.get("/config")
async def get_config():
    return {
        "openrouter_api_key": runtime_config.openrouter_api_key,
        "agent_settings": runtime_config.agent_settings,
        "active_agents": runtime_config.active_agents,
        "available_agents": get_available_agents()
    }

@app.post("/config/save")
async def save_config(req: UpdateConfigRequest):
    runtime_config.openrouter_api_key = req.openrouter_api_key
    runtime_config.agent_settings = req.agent_settings
    runtime_config.active_agents = req.active_agents
    runtime_config.save()
    return {"status": "success"}

@app.post("/agents/create")
async def create_agent(req: CreateAgentRequest):
    agent_dir = Path("agents") / req.agent_id
    if agent_dir.exists():
        raise HTTPException(status_code=400, detail="Agent already exists")
    
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.md").write_text(req.directives, encoding="utf-8")
    
    if req.agent_id not in runtime_config.agent_settings:
        runtime_config.agent_settings[req.agent_id] = AgentModelConfig()
        runtime_config.save()
        
    return {"status": "success", "agent_id": req.agent_id}

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    agent_dir = Path("agents") / agent_id
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    
    shutil.rmtree(agent_dir)
    if agent_id in runtime_config.active_agents:
        runtime_config.active_agents.remove(agent_id)
    if agent_id in runtime_config.agent_settings:
        del runtime_config.agent_settings[agent_id]
    
    runtime_config.save()
    return {"status": "success"}

# --- Streaming Logic ---

async def god_streamer(task: str, thread_id: str) -> AsyncGenerator[str, None]:
    """Main debate stream"""
    queue = asyncio.Queue()
    dynamic_workflow = create_gods_workflow()
    
    initial_state = {
        "messages": [HumanMessage(content=task, name="user")],
        "current_speaker": "",
        "debate_round": 0,
        "inbox": {},
        "context": task,
        "next_step": ""
    }
    config = {"configurable": {"thread_id": thread_id}}

    def sync_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for event in dynamic_workflow.stream(initial_state, config):
                for node, state in event.items():
                    if "messages" in state and state["messages"]:
                        last_msg = state["messages"][-1]
                        data = {
                            "node": node,
                            "speaker": getattr(last_msg, 'name', node),
                            "content": last_msg.content,
                            "round": state.get("debate_round", 0)
                        }
                        asyncio.run_coroutine_threadsafe(queue.put(data), main_loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), main_loop)
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            asyncio.run_coroutine_threadsafe(queue.put({"error": str(e)}), main_loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), main_loop)

    main_loop = asyncio.get_running_loop()
    main_loop.run_in_executor(executor, sync_worker)

    while True:
        try:
            data = await asyncio.wait_for(queue.get(), timeout=30.0)
            if data is None: break
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield ": ping\n\n"

async def private_streamer(agent_id: str, message: str, thread_id: str) -> AsyncGenerator[str, None]:
    """Private session stream"""
    queue = asyncio.Queue()
    private_workflow = create_private_workflow(agent_id)
    
    initial_state = {
        "messages": [HumanMessage(content=message, name="user")],
        "current_speaker": "user",
        "debate_round": 0,
        "inbox": {},
        "context": f"Private chat with {agent_id}",
        "next_step": "continue"
    }
    config = {"configurable": {"thread_id": thread_id}}

    def sync_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for event in private_workflow.stream(initial_state, config):
                for node, state in event.items():
                    if "messages" in state and state["messages"]:
                        last_msg = state["messages"][-1]
                        data = {
                            "node": agent_id,
                            "speaker": agent_id,
                            "content": last_msg.content,
                            "type": "intermediate" if state.get("next_step") == "continue" else "final"
                        }
                        asyncio.run_coroutine_threadsafe(queue.put(data), main_loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), main_loop)
        except Exception as e:
            logger.error(f"Private chat error: {e}")
            asyncio.run_coroutine_threadsafe(queue.put({"error": str(e)}), main_loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), main_loop)

    main_loop = asyncio.get_running_loop()
    main_loop.run_in_executor(executor, sync_worker)

    while True:
        try:
            data = await asyncio.wait_for(queue.get(), timeout=30.0)
            if data is None: break
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield ": ping\n\n"

@app.post("/oracle")
async def oracle_endpoint(request: OracleRequest):
    return StreamingResponse(god_streamer(request.task, request.thread_id), media_type="text/event-stream")

@app.post("/chat/private")
async def private_chat_endpoint(request: PrivateChatRequest):
    return StreamingResponse(private_streamer(request.agent_id, request.message, request.thread_id), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
