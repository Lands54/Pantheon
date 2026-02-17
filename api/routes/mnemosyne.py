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


class TemplateUpsertRequest(BaseModel):
    project_id: str | None = None
    template: str = Field(default="", max_length=12000)


class PolicyRuleUpsertRequest(BaseModel):
    project_id: str | None = None
    to_chronicle: bool | None = None
    to_runtime_log: bool | None = None
    chronicle_template_key: str | None = None
    runtime_log_template_key: str | None = None


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


@router.get("/templates")
async def mnemo_templates(project_id: str | None = None) -> dict:
    return mnemosyne_service.list_templates(project_id=project_id)


@router.put("/templates/{scope}/{key}")
async def mnemo_template_upsert(scope: str, key: str, req: TemplateUpsertRequest) -> dict:
    return mnemosyne_service.upsert_template(
        project_id=req.project_id,
        scope=scope,
        key=key,
        template=req.template,
    )


@router.get("/memory-policy")
async def mnemo_memory_policy(project_id: str | None = None) -> dict:
    return mnemosyne_service.list_policy(project_id=project_id)


@router.put("/memory-policy/{intent_key}")
async def mnemo_memory_policy_upsert(intent_key: str, req: PolicyRuleUpsertRequest) -> dict:
    return mnemosyne_service.update_policy_rule(
        project_id=req.project_id,
        intent_key=intent_key,
        to_chronicle=req.to_chronicle,
        to_runtime_log=req.to_runtime_log,
        chronicle_template_key=req.chronicle_template_key,
        runtime_log_template_key=req.runtime_log_template_key,
    )


@router.get("/template-vars")
async def mnemo_template_vars(project_id: str | None = None, intent_key: str = "") -> dict:
    return mnemosyne_service.list_template_vars(project_id=project_id, intent_key=intent_key)
