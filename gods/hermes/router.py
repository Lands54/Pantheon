"""Provider router for Hermes protocols."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from gods.hermes.errors import HermesError, HERMES_PROVIDER_ERROR, HERMES_BAD_REQUEST
from gods.hermes.models import ProtocolSpec


def _ensure_agent_exists(project_id: str, agent_id: str):
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    if not agent_dir.exists():
        raise HermesError(
            HERMES_PROVIDER_ERROR,
            f"Provider agent '{agent_id}' not found in project '{project_id}'",
            retryable=False,
        )


def _assert_local_http_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HermesError(HERMES_PROVIDER_ERROR, "HTTP provider URL must start with http:// or https://")
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise HermesError(
            HERMES_PROVIDER_ERROR,
            f"HTTP provider host '{host}' is not allowed. Use localhost/127.0.0.1/::1 only.",
        )


def route_provider(spec: ProtocolSpec, project_id: str, payload: dict[str, Any], timeout_sec: int = 30) -> Any:
    provider = spec.provider
    if provider.project_id != project_id:
        raise HermesError(
            HERMES_BAD_REQUEST,
            "Cross-project routing is forbidden in Hermes",
            retryable=False,
            details={"provider_project": provider.project_id, "request_project": project_id},
        )

    if provider.type == "agent_tool":
        from gods.agents.base import GodAgent

        if not provider.agent_id.strip() or not provider.tool_name.strip():
            raise HermesError(HERMES_PROVIDER_ERROR, "agent_tool provider requires agent_id and tool_name")
        _ensure_agent_exists(project_id, provider.agent_id)
        agent = GodAgent(agent_id=provider.agent_id, project_id=project_id)
        args = payload if isinstance(payload, dict) else {}
        result = agent.execute_tool(provider.tool_name, dict(args))
        return {"result": result}

    if provider.type == "http":
        url = (provider.url or "").strip()
        method = (provider.method or "POST").upper()
        _assert_local_http_url(url)
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise HermesError(HERMES_PROVIDER_ERROR, f"Unsupported HTTP method: {method}")
        body = payload if isinstance(payload, dict) else {}
        try:
            if method in {"GET", "DELETE"}:
                resp = requests.request(method=method, url=url, params=body, timeout=max(1, timeout_sec))
            else:
                resp = requests.request(method=method, url=url, json=body, timeout=max(1, timeout_sec))
        except requests.RequestException as e:
            raise HermesError(HERMES_PROVIDER_ERROR, f"HTTP provider request failed: {e}", retryable=True)
        try:
            parsed_body = resp.json()
        except Exception:
            parsed_body = resp.text
        return {
            "result": parsed_body,
            "status_code": resp.status_code,
        }

    raise HermesError(HERMES_PROVIDER_ERROR, f"Unsupported provider type: {provider.type}")
