"""Hermes use-case service."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.hermes import facade as hermes_facade


def _raise_from_domain_error(e: Exception, status_code: int = 400):
    if hasattr(e, "to_dict"):
        raise HTTPException(status_code=status_code, detail=e.to_dict()) from e
    raise HTTPException(status_code=status_code, detail=str(e)) from e


class HermesService:
    def register_protocol(self, project_id: str | None, spec_payload: dict[str, Any]) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            spec = hermes_facade.ProtocolSpec(**spec_payload)
            if spec.provider.project_id != pid:
                raise HTTPException(status_code=400, detail="provider.project_id must equal request project_id")
            if spec.provider.type == "agent_tool" and not hermes_facade.allow_agent_tool_provider(pid):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "HERMES_AGENT_TOOL_DISABLED",
                        "message": "agent_tool provider is disabled by default for this project. Use http provider or enable hermes_allow_agent_tool_provider.",
                    },
                )
            hermes_facade.register_protocol(pid, spec)
            return {"status": "success", "project_id": pid, "protocol": spec.model_dump()}
        except HTTPException:
            raise
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def list_protocols(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        rows = [s.model_dump() for s in hermes_facade.list_protocols(pid)]
        return {"project_id": pid, "protocols": rows}

    def invoke(
        self,
        project_id: str | None,
        caller_id: str,
        name: str,
        mode: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            invoke_req = hermes_facade.InvokeRequest(
                project_id=pid,
                caller_id=caller_id,
                name=name,
                mode=mode,
                payload=payload,
            )
            spec = hermes_facade.get_protocol(pid, invoke_req.name)
            if spec.provider.type == "agent_tool" and not hermes_facade.allow_agent_tool_provider(pid):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "HERMES_AGENT_TOOL_DISABLED",
                        "message": "agent_tool provider invocation is disabled for this project.",
                    },
                )
            result = hermes_facade.invoke(invoke_req)
            return result.model_dump()
        except HTTPException:
            raise
        except Exception as e:
            _raise_from_domain_error(e, status_code=500)

    def get_job(self, job_id: str, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        job = hermes_facade.get_job(pid, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found in project '{pid}'")
        return {"project_id": pid, "job": job.model_dump()}

    def list_invocations(self, project_id: str | None = None, name: str = "", limit: int = 100) -> dict[str, Any]:
        pid = resolve_project(project_id)
        rows = hermes_facade.list_invocations(pid, name=name, limit=limit)
        return {"project_id": pid, "invocations": rows}

    def route_invoke(
        self,
        project_id: str | None,
        caller_id: str,
        target_agent: str,
        function_id: str,
        mode: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            result = hermes_facade.route(
                project_id=pid,
                caller_id=caller_id,
                target_agent=target_agent,
                function_id=function_id,
                payload=payload,
                mode=mode,
            )
            return result.model_dump()
        except Exception as e:
            _raise_from_domain_error(e, status_code=500)

    def register_contract(self, project_id: str | None, contract: dict[str, Any]) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            payload = hermes_facade.register_contract(pid, contract)
            return {"status": "success", "project_id": pid, "contract": payload}
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def commit_contract(self, project_id: str | None, title: str, version: str, agent_id: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            payload = hermes_facade.commit_contract(pid, title, version, agent_id)
            return {"status": "success", "project_id": pid, "contract": payload}
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def list_contracts(self, project_id: str | None = None, include_disabled: bool = False) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return {"project_id": pid, "contracts": hermes_facade.list_contracts(pid, include_disabled=include_disabled)}

    def disable_contract(
        self,
        project_id: str | None,
        title: str,
        version: str,
        agent_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            payload = hermes_facade.disable_contract(pid, title, version, agent_id, reason=reason)
            return {"status": "success", "project_id": pid, "contract": payload}
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def reserve_port(
        self,
        project_id: str | None,
        owner_id: str,
        preferred_port: int | None = None,
        min_port: int = 12000,
        max_port: int = 19999,
        note: str = "",
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            lease = hermes_facade.reserve_port(
                project_id=pid,
                owner_id=owner_id,
                preferred_port=preferred_port,
                min_port=min_port,
                max_port=max_port,
                note=note,
            )
            return {"project_id": pid, "lease": lease}
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def release_port(self, project_id: str | None, owner_id: str, port: int | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        try:
            released = hermes_facade.release_port(project_id=pid, owner_id=owner_id, port=port)
            return {"project_id": pid, "released": released}
        except Exception as e:
            _raise_from_domain_error(e, status_code=400)

    def list_ports(self, project_id: str | None = None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        return {"project_id": pid, "leases": hermes_facade.list_ports(pid)}

    def events_since(self, project_id: str | None, seq: int, limit: int = 200) -> list[dict[str, Any]]:
        pid = resolve_project(project_id)
        return hermes_facade.events_since(pid, seq=seq, limit=limit)


hermes_service = HermesService()
