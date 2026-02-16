"""Hermes bus tools for agents."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from gods.config import runtime_config
from gods.hermes.policy import allow_agent_tool_provider


def _resolve_project(project_id: str | None) -> str:
    pid = project_id or runtime_config.current_project
    if pid not in runtime_config.projects:
        raise ValueError(f"Project '{pid}' not found")
    return pid


@tool
def call_protocol(
    name: str,
    payload_json: str,
    mode: str = "sync",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Call protocol via Hermes bus. Payload is JSON string."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError
        from gods.hermes.models import InvokeRequest

        pid = _resolve_project(project_id)
        payload = json.loads(payload_json) if payload_json.strip() else {}
        req = InvokeRequest(
            project_id=pid,
            caller_id=caller_id,
            name=name,
            mode=("async" if mode == "async" else "sync"),
            payload=payload,
        )
        spec = hermes_service.registry.get(pid, req.name)
        if spec.provider.type == "agent_tool" and not allow_agent_tool_provider(pid):
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "HERMES_AGENT_TOOL_DISABLED",
                        "message": "agent_tool provider invocation is disabled for this project.",
                    },
                },
                ensure_ascii=False,
            )
        result = hermes_service.invoke(req)
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def route_protocol(
    target_agent: str,
    function_id: str,
    payload_json: str = "{}",
    mode: str = "sync",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Route invoke by target agent + function id (Hermes(agent,function,payload))."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        payload = json.loads(payload_json) if payload_json.strip() else {}
        result = hermes_service.route(
            project_id=pid,
            caller_id=caller_id,
            target_agent=target_agent,
            function_id=function_id,
            payload=payload,
            mode=("async" if mode == "async" else "sync"),
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def check_protocol_job(job_id: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Check async protocol job status by job id."""
    try:
        from gods.hermes.service import hermes_service

        pid = _resolve_project(project_id)
        job = hermes_service.get_job(pid, job_id)
        if not job:
            return json.dumps({"ok": False, "error": f"job not found: {job_id}"}, ensure_ascii=False)
        return json.dumps({"ok": True, "job": job.model_dump()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def register_contract(contract_json: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Register structured contract JSON for obligations and committer resolution."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        contract = json.loads(contract_json)
        if isinstance(contract, dict) and not contract.get("submitter"):
            contract["submitter"] = caller_id
        out = hermes_service.contracts.register(pid, contract)
        return json.dumps({"ok": True, "contract": out}, ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def commit_contract(title: str, version: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Commit current agent to a contract version."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        out = hermes_service.contracts.commit(pid, title, version, caller_id)
        return json.dumps({"ok": True, "contract": out}, ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def list_contracts(
    include_disabled: bool = False,
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """List contracts with concise human-readable fields (title/description)."""
    try:
        from gods.hermes.service import hermes_service

        pid = _resolve_project(project_id)
        rows = hermes_service.contracts.list(pid, include_disabled=bool(include_disabled))
        brief = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            brief.append(
                {
                    "version": row.get("version", ""),
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "status": row.get("status", ""),
                    "required_committers": row.get("required_committers", []),
                    "committed_committers": row.get("committed_committers", []),
                    "missing_committers": row.get("missing_committers", []),
                    "is_fully_committed": row.get("is_fully_committed", False),
                }
            )
        return json.dumps({"ok": True, "contracts": brief}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def disable_contract(
    title: str,
    version: str,
    reason: str = "",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Exit current agent from contract committers; contract auto-disables when committers become empty."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        out = hermes_service.contracts.disable(
            pid,
            title=title,
            version=version,
            agent_id=caller_id,
            reason=reason,
        )
        warning = (
            "Warning: disable_contract exits your commitment immediately. "
            "When no committers remain, this contract becomes disabled."
        )
        return json.dumps({"ok": True, "warning": warning, "contract": out}, ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def reserve_port(
    owner_id: str = "",
    preferred_port: int = 0,
    min_port: int = 12000,
    max_port: int = 19999,
    note: str = "",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Reserve a local port lease in Hermes for service startup."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        oid = owner_id.strip() or caller_id
        lease = hermes_service.ports.reserve(
            project_id=pid,
            owner_id=oid,
            preferred_port=(None if int(preferred_port or 0) <= 0 else int(preferred_port)),
            min_port=int(min_port),
            max_port=int(max_port),
            note=note,
        )
        return json.dumps({"ok": True, "lease": lease}, ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def release_port(
    owner_id: str = "",
    port: int = 0,
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Release one or all leases for an owner in current project."""
    try:
        from gods.hermes.service import hermes_service
        from gods.hermes.errors import HermesError

        pid = _resolve_project(project_id)
        oid = owner_id.strip() or caller_id
        removed = hermes_service.ports.release(
            project_id=pid,
            owner_id=oid,
            port=(None if int(port or 0) <= 0 else int(port)),
        )
        return json.dumps({"ok": True, "released": removed}, ensure_ascii=False)
    except HermesError as e:
        return json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def list_port_leases(caller_id: str = "default", project_id: str = "default") -> str:
    """List current project port leases."""
    try:
        from gods.hermes.service import hermes_service

        pid = _resolve_project(project_id)
        rows = hermes_service.ports.list(pid)
        return json.dumps({"ok": True, "leases": rows}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
