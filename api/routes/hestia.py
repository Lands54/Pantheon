"""API Routes - Hestia social graph."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services.hestia_service import hestia_service


router = APIRouter(prefix="/hestia", tags=["hestia"])


class SetEdgeRequest(BaseModel):
    project_id: str | None = None
    from_id: str
    to_id: str
    allowed: bool


class ReplaceGraphRequest(BaseModel):
    project_id: str | None = None
    nodes: list[str] = Field(default_factory=list)
    matrix: dict = Field(default_factory=dict)


@router.get("/graph")
async def get_graph(project_id: str | None = None) -> dict:
    return hestia_service.get_graph(project_id=project_id)


@router.post("/edge")
async def set_edge(req: SetEdgeRequest) -> dict:
    return hestia_service.set_edge(
        project_id=req.project_id,
        from_id=req.from_id,
        to_id=req.to_id,
        allowed=req.allowed,
    )


@router.put("/graph")
async def replace_graph(req: ReplaceGraphRequest) -> dict:
    return hestia_service.replace_graph(project_id=req.project_id, nodes=req.nodes, matrix=req.matrix)
