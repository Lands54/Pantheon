"""Core communication routes for autonomous runtime."""
from fastapi import APIRouter
from fastapi import HTTPException

from api.services import communication_service
from api.models import HumanMessageRequest

router = APIRouter(tags=["communication"])


@router.post("/confess")
async def human_confession(req: HumanMessageRequest):
    """Deliver a private message and optionally enqueue immediate inbox pulse."""
    if not str(req.title or "").strip():
        raise HTTPException(status_code=400, detail="title is required")
    return communication_service.confess(
        agent_id=req.agent_id,
        title=req.title,
        message=req.message,
        silent=bool(req.silent),
    )
