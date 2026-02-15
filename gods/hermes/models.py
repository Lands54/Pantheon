"""Hermes typed models."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


ProviderType = Literal["agent_tool", "http"]
ProtocolMode = Literal["sync", "async", "both"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class ProviderSpec(BaseModel):
    type: ProviderType = "agent_tool"
    project_id: str
    agent_id: str = ""
    tool_name: str = ""
    url: str = ""
    method: str = "POST"

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str):
        if not v or not v.strip():
            raise ValueError("provider.project_id is required")
        return v.strip()


class ProtocolLimits(BaseModel):
    max_concurrency: int = 2
    rate_per_minute: int = 60
    timeout_sec: int = 30


class ProtocolSpec(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    mode: ProtocolMode = "both"
    status: Literal["active", "deprecated", "disabled"] = "active"
    owner_agent: str = ""
    function_id: str = ""
    provider: ProviderSpec
    request_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    response_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    limits: ProtocolLimits = Field(default_factory=ProtocolLimits)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str):
        value = (v or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", value):
            raise ValueError("protocol name must match namespace.action format, e.g. grass.scan")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str):
        value = (v or "").strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise ValueError("version must be semver like 1.0.0")
        return value

    @field_validator("owner_agent", "function_id")
    @classmethod
    def normalize_optional_ids(cls, v: str):
        return (v or "").strip()


class InvokeRequest(BaseModel):
    project_id: str
    caller_id: str
    name: str
    version: str = "1.0.0"
    mode: Literal["sync", "async"] = "sync"
    payload: Dict[str, Any] = Field(default_factory=dict)


class InvokeResult(BaseModel):
    ok: bool
    project_id: str
    name: str
    version: str
    mode: Literal["sync", "async"]
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    job_id: str = ""
    latency_ms: int = 0


class JobRecord(BaseModel):
    job_id: str
    project_id: str
    caller_id: str
    name: str
    version: str
    mode: Literal["async"] = "async"
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = "queued"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    result: Any = None
    error: Optional[Dict[str, Any]] = None
