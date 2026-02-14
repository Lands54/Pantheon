"""
Legacy social routes (broadcast/prayers) backed by LangGraph workflow + sqlite.
These endpoints are optional and can be disabled in config.
"""
from __future__ import annotations

import json
import fcntl
import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from gods.config import runtime_config
from gods.legacy.workflow import create_gods_workflow
from api.models import BroadcastRequest

router = APIRouter(tags=["legacy-social"])
logger = logging.getLogger("GodsServer")
executor = ThreadPoolExecutor(max_workers=20)


async def god_streamer(task: str, thread_id: str, project_id: str = "default") -> AsyncGenerator[str, None]:
    queue = asyncio.Queue()
    dynamic_workflow = create_gods_workflow(project_id)

    initial_state = {
        "project_id": project_id,
        "messages": [HumanMessage(content=task, name="user")],
        "current_speaker": "",
        "debate_round": 0,
        "inbox": {},
        "context": task,
        "next_step": "",
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
                            "speaker": getattr(last_msg, "name", node),
                            "content": last_msg.content,
                            "round": state.get("debate_round", 0),
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
    return StreamingResponse(
        god_streamer(f"SACRED DECREE: {req.message}", req.thread_id, runtime_config.current_project),
        media_type="text/event-stream",
    )


@router.get("/prayers/check")
async def check_prayers():
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

