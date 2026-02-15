"""Mnemosyne API routes for durable archives."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gods.config import runtime_config
from gods.mnemosyne import write_entry, list_entries, read_entry, VALID_VAULTS

router = APIRouter(prefix="/mnemosyne", tags=["mnemosyne"])


class MnemoWriteRequest(BaseModel):
    project_id: str | None = None
    vault: str = "human"
    author: str = "human"
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


def _pick_project(project_id: str | None) -> str:
    pid = project_id or runtime_config.current_project
    if pid not in runtime_config.projects:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    return pid


@router.post("/write")
async def mnemo_write(req: MnemoWriteRequest) -> dict:
    pid = _pick_project(req.project_id)
    if req.vault not in VALID_VAULTS:
        raise HTTPException(status_code=400, detail=f"invalid vault: {req.vault}")
    row = write_entry(pid, req.vault, req.author, req.title, req.content, req.tags)
    return {"status": "success", "project_id": pid, "entry": row}


@router.get("/list")
async def mnemo_list(project_id: str | None = None, vault: str = "human", limit: int = 30) -> dict:
    pid = _pick_project(project_id)
    if vault not in VALID_VAULTS:
        raise HTTPException(status_code=400, detail=f"invalid vault: {vault}")
    rows = list_entries(pid, vault, limit=limit)
    return {"project_id": pid, "vault": vault, "entries": rows}


@router.get("/read/{entry_id}")
async def mnemo_read(entry_id: str, project_id: str | None = None, vault: str = "human") -> dict:
    pid = _pick_project(project_id)
    if vault not in VALID_VAULTS:
        raise HTTPException(status_code=400, detail=f"invalid vault: {vault}")
    row = read_entry(pid, vault, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"project_id": pid, "vault": vault, **row}
