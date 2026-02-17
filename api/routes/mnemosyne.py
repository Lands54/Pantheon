"""Mnemosyne API routes for durable archives."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services import mnemosyne_service

router = APIRouter(prefix="/mnemosyne", tags=["mnemosyne"])


class MnemoWriteRequest(BaseModel):
    project_id: str | None = None
    vault: str = "human"
    author: str = "human"
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


@router.post("/write")
async def mnemo_write(req: MnemoWriteRequest) -> dict:
    return mnemosyne_service.write(
        project_id=req.project_id,
        vault=req.vault,
        author=req.author,
        title=req.title,
        content=req.content,
        tags=req.tags,
    )


@router.get("/list")
async def mnemo_list(project_id: str | None = None, vault: str = "human", limit: int = 30) -> dict:
    return mnemosyne_service.list(project_id=project_id, vault=vault, limit=limit)


@router.get("/read/{entry_id}")
async def mnemo_read(entry_id: str, project_id: str | None = None, vault: str = "human") -> dict:
    return mnemosyne_service.read(entry_id=entry_id, project_id=project_id, vault=vault)
