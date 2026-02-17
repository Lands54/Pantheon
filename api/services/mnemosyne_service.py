"""Mnemosyne use-case service."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.mnemosyne import facade as mnemosyne_facade
from gods.mnemosyne import template_registry
from gods.mnemosyne import policy_registry
from gods.mnemosyne import intent_schema_registry


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

    def list_templates(self, project_id: str | None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return {
            "project_id": pid,
            "runtime_log": template_registry.list_memory_templates(pid, "runtime_log"),
            "chronicle": template_registry.list_memory_templates(pid, "chronicle"),
        }

    def upsert_template(self, project_id: str | None, scope: str, key: str, template: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        if scope not in {"runtime_log", "chronicle"}:
            raise HTTPException(status_code=400, detail="scope must be runtime_log|chronicle")
        try:
            row = template_registry.upsert_memory_template(pid, scope, key, template)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"project_id": pid, **row}

    def list_policy(self, project_id: str | None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return {"project_id": pid, "items": policy_registry.list_policy_rules(pid)}

    def update_policy_rule(
        self,
        project_id: str | None,
        intent_key: str,
        *,
        to_chronicle: bool | None = None,
        to_runtime_log: bool | None = None,
        chronicle_template_key: str | None = None,
        runtime_log_template_key: str | None = None,
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            row = policy_registry.upsert_policy_rule(
                pid,
                intent_key,
                to_chronicle=to_chronicle,
                to_runtime_log=to_runtime_log,
                chronicle_template_key=chronicle_template_key,
                runtime_log_template_key=runtime_log_template_key,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"project_id": pid, "intent_key": intent_key, **row}

    def list_template_vars(self, project_id: str | None, intent_key: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        key = str(intent_key or "").strip()
        if not key:
            raise HTTPException(status_code=400, detail="intent_key is required")
        return {"project_id": pid, **intent_schema_registry.template_vars_for_intent(pid, key)}


mnemosyne_service = MnemosyneService()
