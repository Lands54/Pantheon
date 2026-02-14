"""
API Routes - Communication
Core communication routes for autonomous runtime.
"""
import json
import fcntl
import time
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks

from gods.config import runtime_config
from api.scheduler import pulse_agent_sync
from api.models import HumanMessageRequest

router = APIRouter(tags=["communication"])
logger = logging.getLogger("GodsServer")


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
            try:
                result = pulse_agent_sync(
                    project_id=project_id,
                    agent_id=req.agent_id,
                    reason="human_confess",
                    force=False,
                )
                if result.get("triggered"):
                    logger.info(f"⚡ Auto-Pulse triggered for {req.agent_id} in {project_id}")
                else:
                    logger.info(f"⏸ Pulse skipped for {req.agent_id}: {result.get('reason')}")
            except Exception as e:
                logger.error(f"Auto-Pulse failed for {req.agent_id}: {e}")

        background_tasks.add_task(run_pulse)
        status = "Confession delivered and pulse triggered"
    else:
        status = "Confession delivered silently (no pulse)"
    
    return {"status": status}

