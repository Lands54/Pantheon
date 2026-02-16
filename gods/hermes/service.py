"""Hermes protocol execution bus service."""
from __future__ import annotations

from gods.hermes.executor import HermesExecutor
from gods.hermes.models import ProtocolSpec, InvokeRequest, InvokeResult
from gods.hermes.contracts import HermesContracts
from gods.hermes.errors import HermesError, HERMES_PROTOCOL_NOT_FOUND
from gods.hermes.client import HermesClient
from gods.hermes.ports import HermesPortRegistry


class HermesService:
    """
    Core service orchestrator for the Hermes protocol execution bus.
    """

    def __init__(self):
        self.executor = HermesExecutor()
        self.registry = self.executor.registry
        self.contracts = HermesContracts()
        self.ports = HermesPortRegistry()

    def register(self, project_id: str, spec: ProtocolSpec) -> ProtocolSpec:
        return self.registry.register(project_id, spec)

    def list(self, project_id: str):
        return self.registry.list(project_id)

    def invoke(self, req: InvokeRequest) -> InvokeResult:
        if req.mode == "async":
            return self.executor.invoke_async(req)
        return self.executor.invoke_sync(req)

    def get_job(self, project_id: str, job_id: str):
        return self.executor.get_job(project_id, job_id)

    def list_invocations(self, project_id: str, name: str = "", limit: int = 100):
        return self.executor.list_invocations(project_id, name=name, limit=limit)

    def route(self, project_id: str, caller_id: str, target_agent: str, function_id: str, payload: dict, mode: str = "sync"):
        target_agent = (target_agent or "").strip()
        function_id = (function_id or "").strip()
        if not target_agent or not function_id:
            raise HermesError("HERMES_BAD_REQUEST", "target_agent and function_id are required")

        candidates = [
            p for p in self.registry.list(project_id)
            if (
                p.status == "active"
                and p.owner_agent == target_agent
                and (
                    p.function_id == function_id
                    or p.function_id == f"{target_agent}.{function_id}"
                    or p.function_id.endswith(f".{function_id}")
                )
            )
        ]
        if not candidates:
            raise HermesError(
                HERMES_PROTOCOL_NOT_FOUND,
                f"no routed protocol for {target_agent}.{function_id} in project '{project_id}'",
            )

        best = sorted(candidates, key=lambda p: float(p.updated_at), reverse=True)[0]
        req = InvokeRequest(
            project_id=project_id,
            caller_id=caller_id,
            name=best.name,
            mode=("async" if mode == "async" else "sync"),
            payload=payload or {},
        )
        return self.invoke(req)


hermes_service = HermesService()

__all__ = ["hermes_service", "HermesService", "ProtocolSpec", "InvokeRequest", "InvokeResult", "HermesClient"]
