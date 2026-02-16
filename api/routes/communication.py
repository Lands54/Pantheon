"""Core communication routes for autonomous runtime."""
import logging
from fastapi import APIRouter
from fastapi import HTTPException

from gods.config import runtime_config
from gods.inbox import enqueue_message
from gods.pulse import get_priority_weights, is_inbox_event_enabled
from api.models import HumanMessageRequest

router = APIRouter(tags=["communication"])
logger = logging.getLogger("GodsServer")


@router.post("/confess")
async def human_confession(req: HumanMessageRequest):
    """Deliver a private message and optionally enqueue immediate inbox pulse."""
    if not str(req.title or "").strip():
        raise HTTPException(status_code=400, detail="title is required")
    project_id = runtime_config.current_project
    weights = get_priority_weights(project_id)
    trigger_pulse = (not req.silent) and is_inbox_event_enabled(project_id)
    res = enqueue_message(
        project_id=project_id,
        agent_id=req.agent_id,
        sender="High Overseer",
        title=req.title,
        content=req.message,
        msg_type="confession",
        trigger_pulse=trigger_pulse,
        pulse_priority=int(weights.get("inbox_event", 100)),
    )
    if trigger_pulse:
        logger.info(f"⚡ Inbox event queued for {req.agent_id} in {project_id}")
        status = "Confession delivered and pulse enqueued"
    else:
        status = "Confession delivered silently (no immediate pulse)"
    return {"status": status, **res}
