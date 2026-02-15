"""Hermes SDK client for code-level protocol orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import time

import requests


@dataclass
class HermesClient:
    """
    SDK client for interacting with the Hermes protocol service via HTTP.
    """
    base_url: str = "http://localhost:8000"
    timeout_sec: int = 30
    retries: int = 2
    retry_backoff_sec: float = 0.25

    def _url(self, path: str) -> str:
        """
        Constructs a full URL from the base URL and a given path.
        """
        return f"{self.base_url.rstrip('/')}{path}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Internal helper for making HTTP requests with retry logic.
        """
        attempts = max(0, int(self.retries)) + 1
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                return requests.request(method=method, url=self._url(path), timeout=self.timeout_sec, **kwargs)
            except requests.RequestException as e:
                last_err = e
                if i == attempts - 1:
                    raise
                sleep_sec = float(self.retry_backoff_sec) * (2 ** i)
                time.sleep(max(0.0, sleep_sec))
        assert last_err is not None
        raise last_err

    def register_protocol(self, project_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        """
        Registers a protocol specification via the HTTP API.
        """
        r = self._request(
            "POST",
            "/hermes/register",
            json={"project_id": project_id, "spec": spec},
        )
        r.raise_for_status()
        return r.json()

    def list_protocols(self, project_id: str) -> dict[str, Any]:
        """
        Lists registered protocols for a specific project.
        """
        r = self._request("GET", "/hermes/list", params={"project_id": project_id})
        r.raise_for_status()
        return r.json()

    def invoke(self, project_id: str, caller_id: str, name: str, payload: dict[str, Any], version: str = "1.0.0", mode: str = "sync") -> dict[str, Any]:
        """
        Invokes a specific protocol by name and version.
        """
        r = self._request(
            "POST",
            "/hermes/invoke",
            json={
                "project_id": project_id,
                "caller_id": caller_id,
                "name": name,
                "version": version,
                "mode": mode,
                "payload": payload,
            },
        )
        r.raise_for_status()
        return r.json()

    def route(self, project_id: str, caller_id: str, target_agent: str, function_id: str, payload: dict[str, Any], mode: str = "sync") -> dict[str, Any]:
        """
        Routes an invocation based on target agent and function ID.
        """
        r = self._request(
            "POST",
            "/hermes/route",
            json={
                "project_id": project_id,
                "caller_id": caller_id,
                "target_agent": target_agent,
                "function_id": function_id,
                "mode": mode,
                "payload": payload,
            },
        )
        r.raise_for_status()
        return r.json()

    def get_job(self, project_id: str, job_id: str) -> dict[str, Any]:
        """
        Retrieves the status of an asynchronous job.
        """
        r = self._request("GET", f"/hermes/jobs/{job_id}", params={"project_id": project_id})
        r.raise_for_status()
        return r.json()

    def list_invocations(self, project_id: str, name: str = "", limit: int = 100) -> dict[str, Any]:
        """
        Lists invocation records for a project.
        """
        params: dict[str, Any] = {"project_id": project_id, "limit": int(limit)}
        if name:
            params["name"] = name
        r = self._request("GET", "/hermes/invocations", params=params)
        r.raise_for_status()
        return r.json()

    def register_contract(self, project_id: str, contract: dict[str, Any]) -> dict[str, Any]:
        """
        Registers a contract specification.
        """
        r = self._request(
            "POST",
            "/hermes/contracts/register",
            json={"project_id": project_id, "contract": contract},
        )
        r.raise_for_status()
        return r.json()

    def commit_contract(self, project_id: str, title: str, version: str, agent_id: str) -> dict[str, Any]:
        """
        Allows an agent to commit to a contract.
        """
        r = self._request(
            "POST",
            "/hermes/contracts/commit",
            json={"project_id": project_id, "title": title, "version": version, "agent_id": agent_id},
        )
        r.raise_for_status()
        return r.json()

    def resolve_contract(self, project_id: str, title: str, version: str) -> dict[str, Any]:
        """
        Resolves effective obligations for a contract.
        """
        r = self._request(
            "GET",
            "/hermes/contracts/resolved",
            params={"project_id": project_id, "title": title, "version": version},
        )
        r.raise_for_status()
        return r.json()

    def list_contracts(self, project_id: str, include_disabled: bool = False) -> dict[str, Any]:
        """
        Lists contracts, optionally including disabled contracts.
        """
        r = self._request(
            "GET",
            "/hermes/contracts/list",
            params={"project_id": project_id, "include_disabled": bool(include_disabled)},
        )
        r.raise_for_status()
        return r.json()

    def disable_contract(
        self,
        project_id: str,
        title: str,
        version: str,
        agent_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Exits commitment for a contract; contract auto-disables when committers become empty.
        """
        r = self._request(
            "POST",
            "/hermes/contracts/disable",
            json={
                "project_id": project_id,
                "title": title,
                "version": version,
                "agent_id": agent_id,
                "reason": reason,
            },
        )
        r.raise_for_status()
        return r.json()

    def reserve_port(
        self,
        project_id: str,
        owner_id: str,
        preferred_port: int | None = None,
        min_port: int = 12000,
        max_port: int = 19999,
        note: str = "",
    ) -> dict[str, Any]:
        """
        Reserves a network port for an agent.
        """
        r = self._request(
            "POST",
            "/hermes/ports/reserve",
            json={
                "project_id": project_id,
                "owner_id": owner_id,
                "preferred_port": preferred_port,
                "min_port": min_port,
                "max_port": max_port,
                "note": note,
            },
        )
        r.raise_for_status()
        return r.json()

    def release_port(self, project_id: str, owner_id: str, port: int | None = None) -> dict[str, Any]:
        """
        Releases a previously reserved network port.
        """
        r = self._request(
            "POST",
            "/hermes/ports/release",
            json={"project_id": project_id, "owner_id": owner_id, "port": port},
        )
        r.raise_for_status()
        return r.json()

    def list_ports(self, project_id: str) -> dict[str, Any]:
        """
        Lists all reserved ports for a project.
        """
        r = self._request("GET", "/hermes/ports/list", params={"project_id": project_id})
        r.raise_for_status()
        return r.json()

    def wait_job(self, project_id: str, job_id: str, timeout_sec: int = 60, poll_sec: float = 0.5) -> dict[str, Any]:
        """
        Polls a job until it succeeds, fails, or times out.
        """
        deadline = time.time() + max(1, int(timeout_sec))
        while True:
            data = self.get_job(project_id, job_id)
            st = ((data or {}).get("job") or {}).get("status")
            if st in {"succeeded", "failed"}:
                return data
            if time.time() >= deadline:
                raise TimeoutError(f"Hermes job wait timeout: {job_id}")
            time.sleep(max(0.05, float(poll_sec)))
