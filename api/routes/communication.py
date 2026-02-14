"""
API Routes - Communication
Handles broadcast, confess, and prayers endpoints.
"""
import json
import fcntl
import time
import asyncio
import logging
from typing import AsyncGenerator
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from concurrent.futures import ThreadPoolExecutor

from gods.config import runtime_config
from gods.workflow import create_gods_workflow, create_private_workflow
from api.models import BroadcastRequest, HumanMessageRequest

router = APIRouter(tags=["communication"])
logger = logging.getLogger("GodsServer")
executor = ThreadPoolExecutor(max_workers=20)


async def god_streamer(task: str, thread_id: str, project_id: str = "default") -> AsyncGenerator[str, None]:
    """Main debate stream for a specific project."""
    queue = asyncio.Queue()
    dynamic_workflow = create_gods_workflow(project_id)
    
    initial_state = {
        "project_id": project_id,
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
            if data is None:
                break
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield ": ping\n\n"


@router.post("/broadcast")
async def broadcast_decree(req: BroadcastRequest):
    """Deliver a Sacred Decree to the Public Synod of the current project."""
    return StreamingResponse(
        god_streamer(f"SACRED DECREE: {req.message}", req.thread_id, runtime_config.current_project),
        media_type="text/event-stream"
    )


@router.post("/confess")
async def human_confession(req: HumanMessageRequest, background_tasks: BackgroundTasks):
    """Deliver a private message and trigger an immediate autonomous pulse."""
    project_id = runtime_config.current_project
    buffer_dir = Path("projects") / project_id / "buffers"
    buffer_dir.mkdir(parents=True, exist_ok=True)
    target_buffer = buffer_dir / f"{req.agent_id}.jsonl"
    
    msg_data = {
        "timestamp": time.time(),
        "from": "High Overseer",
        "type": "confession",
        "content": req.message
    }
    
    # 1. Store the message in the buffer
    with open(target_buffer, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(msg_data, ensure_ascii=False) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    
    # 2. Trigger an immediate pulse for this agent (if not silent)
    if not req.silent:
        def run_pulse():
            from gods.agents.base import GodAgent
            try:
                agent = GodAgent(agent_id=req.agent_id, project_id=project_id)
                state = {
                    "project_id": project_id,
                    "messages": [HumanMessage(content=f"PRIVATE REVELATION: {req.message}", name="High Overseer")],
                    "context": f"Private interaction with High Overseer: {req.message}",
                    "next_step": ""
                }
                agent.process(state)
                logger.info(f"⚡ Auto-Pulse triggered for {req.agent_id} in {project_id}")
            except Exception as e:
                logger.error(f"Auto-Pulse failed for {req.agent_id}: {e}")

        background_tasks.add_task(run_pulse)
        status = "Confession delivered and pulse triggered"
    else:
        status = "Confession delivered silently (no pulse)"
    
    return {"status": status}


@router.get("/prayers/check")
async def check_prayers():
    """Human check for messages sent by Agents (Prayers) in current project."""
    project_id = runtime_config.current_project
    buffer_path = Path("projects") / project_id / "buffers" / "human.jsonl"
    if not buffer_path.exists():
        return {"prayers": []}
    
    prayers = []
    with open(buffer_path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        for line in f:
            if line.strip():
                prayers.append(json.loads(line))
        fcntl.flock(f, fcntl.LOCK_UN)
    return {"prayers": prayers}
