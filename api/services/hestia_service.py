"""Hestia API use-case service."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.hestia import facade as hestia_facade
from gods.identity import is_valid_agent_id


class HestiaService:
    def get_graph(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        graph = hestia_facade.get_social_graph(pid)
        return {"project_id": pid, "graph": graph}

    def set_edge(self, project_id: str | None, from_id: str, to_id: str, allowed: bool) -> dict[str, Any]:
        pid = resolve_project(project_id)
        src = str(from_id or "").strip()
        dst = str(to_id or "").strip()
        if not is_valid_agent_id(src) or not is_valid_agent_id(dst):
            raise HTTPException(status_code=400, detail="from_id/to_id must be valid agent ids")
        try:
            graph = hestia_facade.set_social_edge(project_id=pid, from_id=src, to_id=dst, allowed=bool(allowed))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {
            "project_id": pid,
            "updated": {"from_id": src, "to_id": dst, "allowed": bool(allowed)},
            "graph": graph,
        }

    def replace_graph(self, project_id: str | None, nodes: list[str], matrix: dict) -> dict[str, Any]:
        pid = resolve_project(project_id)
        graph = hestia_facade.replace_social_graph(project_id=pid, nodes=nodes, matrix=matrix)
        return {"project_id": pid, "graph": graph}


hestia_service = HestiaService()
