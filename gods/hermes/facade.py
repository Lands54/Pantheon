"""Public facade for hermes domain operations."""
from __future__ import annotations

from typing import Any

from gods.hermes.client import HermesClient
from gods.hermes.errors import (
    HERMES_BAD_REQUEST,
    HERMES_BUSY,
    HERMES_PROTOCOL_NOT_FOUND,
    HERMES_RATE_LIMITED,
    HERMES_SCHEMA_INVALID,
    HermesError,
)
from gods.hermes.events import hermes_events
from gods.hermes.executor import HermesExecutor
from gods.hermes.limits import HermesLimiter
from gods.hermes.models import InvokeRequest, ProtocolSpec
from gods.hermes.policy import allow_agent_tool_provider
from gods.hermes.ports import HermesPortRegistry
from gods.hermes.registry import HermesRegistry
from gods.hermes.schema import validate_schema
from gods.hermes.service import hermes_service


def register_protocol(project_id: str, spec: ProtocolSpec):
    hermes_service.register(project_id, spec)


def list_protocols(project_id: str) -> list[ProtocolSpec]:
    return hermes_service.list(project_id)


def get_protocol(project_id: str, name: str) -> ProtocolSpec:
    return hermes_service.registry.get(project_id, name)


def invoke(req: InvokeRequest):
    return hermes_service.invoke(req)


def route(
    project_id: str,
    caller_id: str,
    target_agent: str,
    function_id: str,
    payload: dict[str, Any],
    mode: str = "sync",
):
    return hermes_service.route(
        project_id=project_id,
        caller_id=caller_id,
        target_agent=target_agent,
        function_id=function_id,
        payload=payload,
        mode=mode,
    )


def get_job(project_id: str, job_id: str):
    return hermes_service.get_job(project_id, job_id)


def list_invocations(project_id: str, name: str = "", limit: int = 100) -> list[dict[str, Any]]:
    return hermes_service.list_invocations(project_id, name=name, limit=limit)


def register_contract(project_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    return hermes_service.contracts.register(project_id, contract)


def commit_contract(project_id: str, title: str, version: str, agent_id: str) -> dict[str, Any]:
    return hermes_service.contracts.commit(project_id, title, version, agent_id)


def list_contracts(project_id: str, include_disabled: bool = False) -> list[dict[str, Any]]:
    return hermes_service.contracts.list(project_id, include_disabled=include_disabled)


def disable_contract(project_id: str, title: str, version: str, agent_id: str, reason: str = "") -> dict[str, Any]:
    return hermes_service.contracts.disable(project_id, title, version, agent_id, reason=reason)


def reserve_port(
    project_id: str,
    owner_id: str,
    preferred_port: int | None = None,
    min_port: int = 12000,
    max_port: int = 19999,
    note: str = "",
) -> dict[str, Any]:
    return hermes_service.ports.reserve(
        project_id=project_id,
        owner_id=owner_id,
        preferred_port=preferred_port,
        min_port=min_port,
        max_port=max_port,
        note=note,
    )


def release_port(project_id: str, owner_id: str, port: int | None = None) -> list[dict[str, Any]]:
    return hermes_service.ports.release(project_id=project_id, owner_id=owner_id, port=port)


def list_ports(project_id: str) -> list[dict[str, Any]]:
    return hermes_service.ports.list(project_id)


def events_since(project_id: str, seq: int, limit: int = 200) -> list[dict[str, Any]]:
    return hermes_events.get_since(seq, project_id=project_id, limit=limit)


__all__ = [
    "HermesError",
    "HERMES_BAD_REQUEST",
    "HERMES_BUSY",
    "HERMES_PROTOCOL_NOT_FOUND",
    "HERMES_RATE_LIMITED",
    "HERMES_SCHEMA_INVALID",
    "HermesLimiter",
    "HermesPortRegistry",
    "HermesExecutor",
    "HermesRegistry",
    "validate_schema",
    "HermesClient",
    "hermes_service",
    "ProtocolSpec",
    "InvokeRequest",
    "allow_agent_tool_provider",
    "register_protocol",
    "list_protocols",
    "get_protocol",
    "invoke",
    "route",
    "get_job",
    "list_invocations",
    "register_contract",
    "commit_contract",
    "list_contracts",
    "disable_contract",
    "reserve_port",
    "release_port",
    "list_ports",
    "events_since",
]
