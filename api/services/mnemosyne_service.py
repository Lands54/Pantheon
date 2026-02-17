"""Mnemosyne use-case service."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.mnemosyne import facade as mnemosyne_facade


class MnemosyneService:
    def write(
        self,
        project_id: str | None,
        vault: str,
        author: str,
        title: str,
        content: str,
        tags: list[str],
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        if vault not in mnemosyne_facade.VALID_VAULTS:
            raise HTTPException(status_code=400, detail=f"invalid vault: {vault}")
        row = mnemosyne_facade.write_entry(pid, vault, author, title, content, tags)
        return {"status": "success", "project_id": pid, "entry": row}

    def list(self, project_id: str | None, vault: str = "human", limit: int = 30) -> dict[str, Any]:
        pid = resolve_project(project_id)
        if vault not in mnemosyne_facade.VALID_VAULTS:
            raise HTTPException(status_code=400, detail=f"invalid vault: {vault}")
        rows = mnemosyne_facade.list_entries(pid, vault, limit=limit)
        return {"project_id": pid, "vault": vault, "entries": rows}

    def read(self, entry_id: str, project_id: str | None, vault: str = "human") -> dict[str, Any]:
        pid = resolve_project(project_id)
        if vault not in mnemosyne_facade.VALID_VAULTS:
            raise HTTPException(status_code=400, detail=f"invalid vault: {vault}")
        row = mnemosyne_facade.read_entry(pid, vault, entry_id)
        if not row:
            raise HTTPException(status_code=404, detail="entry not found")
        return {"project_id": pid, "vault": vault, **row}


mnemosyne_service = MnemosyneService()
