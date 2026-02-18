"""Mnemosyne API routes for durable archives."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import base64
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
    to_llm_context: bool | None = None
    chronicle_template_key: str | None = None
    runtime_log_template_key: str | None = None
    llm_context_template_key: str | None = None


class ArtifactTextPutRequest(BaseModel):
    project_id: str | None = None
    scope: str = "agent"
    owner_agent_id: str = ""
    actor_id: str = "human"
    content: str
    mime: str = "text/plain"
    tags: list[str] = Field(default_factory=list)


class ArtifactBytesPutRequest(BaseModel):
    project_id: str | None = None
    scope: str = "agent"
    owner_agent_id: str = ""
    actor_id: str = "human"
    content_base64: str
    mime: str = "application/octet-stream"
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
        to_llm_context=req.to_llm_context,
        chronicle_template_key=req.chronicle_template_key,
        runtime_log_template_key=req.runtime_log_template_key,
        llm_context_template_key=req.llm_context_template_key,
    )


@router.get("/template-vars")
async def mnemo_template_vars(project_id: str | None = None, intent_key: str = "") -> dict:
    return mnemosyne_service.list_template_vars(project_id=project_id, intent_key=intent_key)


@router.get("/artifacts")
async def mnemo_artifact_list(
    project_id: str | None = None,
    scope: str = "project",
    actor_id: str = "human",
    owner_agent_id: str = "",
    limit: int = 50,
) -> dict:
    return mnemosyne_service.list_artifacts(
        project_id=project_id,
        scope=scope,
        actor_id=actor_id,
        owner_agent_id=owner_agent_id,
        limit=limit,
    )


@router.get("/artifacts/{artifact_id}")
async def mnemo_artifact_head(artifact_id: str, project_id: str | None = None, actor_id: str = "human") -> dict:
    return mnemosyne_service.head_artifact(project_id=project_id, artifact_id=artifact_id, actor_id=actor_id)


@router.post("/artifacts/text")
async def mnemo_artifact_put_text(req: ArtifactTextPutRequest) -> dict:
    return mnemosyne_service.put_artifact_text(
        project_id=req.project_id,
        scope=req.scope,
        owner_agent_id=req.owner_agent_id,
        actor_id=req.actor_id,
        content=req.content,
        mime=req.mime,
        tags=req.tags,
    )


@router.post("/artifacts/bytes")
async def mnemo_artifact_put_bytes(req: ArtifactBytesPutRequest) -> dict:
    try:
        data = base64.b64decode(str(req.content_base64 or "").encode("utf-8"), validate=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid content_base64: {e}") from e
    return mnemosyne_service.put_artifact_bytes(
        project_id=req.project_id,
        scope=req.scope,
        owner_agent_id=req.owner_agent_id,
        actor_id=req.actor_id,
        data=data,
        mime=req.mime,
        tags=req.tags,
    )
