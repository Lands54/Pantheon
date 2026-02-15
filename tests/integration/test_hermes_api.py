from __future__ import annotations

import time

from fastapi.testclient import TestClient

from api.server import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def _set_agent_tool_provider(project_id: str, enabled: bool):
    cfg = client.get("/config").json()
    cfg["projects"][project_id]["hermes_allow_agent_tool_provider"] = bool(enabled)
    client.post("/config/save", json=cfg)


def test_hermes_register_and_invoke_sync_async():
    project_id = "test_hermes_api_world"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        _set_agent_tool_provider(project_id, True)
        client.post("/agents/create", json={"agent_id": "alpha", "directives": "# alpha"})

        spec = {
            "name": "alpha.list",
            "version": "1.0.0",
            "mode": "both",
            "provider": {
                "type": "agent_tool",
                "project_id": project_id,
                "agent_id": "alpha",
                "tool_name": "list_dir",
            },
            "request_schema": {"type": "object"},
            "response_schema": {
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            },
        }
        reg = client.post("/hermes/register", json={"project_id": project_id, "spec": spec})
        assert reg.status_code == 200

        sync_res = client.post(
            "/hermes/invoke",
            json={
                "project_id": project_id,
                "caller_id": "tester",
                "name": "alpha.list",
                "version": "1.0.0",
                "mode": "sync",
                "payload": {"path": "."},
            },
        )
        assert sync_res.status_code == 200
        assert sync_res.json().get("ok") is True

        async_res = client.post(
            "/hermes/invoke",
            json={
                "project_id": project_id,
                "caller_id": "tester",
                "name": "alpha.list",
                "version": "1.0.0",
                "mode": "async",
                "payload": {"path": "."},
            },
        )
        assert async_res.status_code == 200
        job_id = async_res.json().get("job_id")
        assert job_id

        final_status = None
        for _ in range(30):
            job_res = client.get(f"/hermes/jobs/{job_id}", params={"project_id": project_id})
            if job_res.status_code == 200:
                st = job_res.json().get("job", {}).get("status")
                if st in {"succeeded", "failed"}:
                    final_status = st
                    break
            time.sleep(0.1)
        assert final_status in {"succeeded", "failed"}

        hist = client.get("/hermes/invocations", params={"project_id": project_id, "name": "alpha.list", "limit": 10})
        assert hist.status_code == 200
        assert len(hist.json().get("invocations", [])) >= 1
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")


def test_hermes_agent_tool_disabled_by_default():
    project_id = "test_hermes_agent_tool_disabled_default"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "alpha", "directives": "# alpha"})

        spec = {
            "name": "alpha.list",
            "version": "1.0.0",
            "mode": "both",
            "provider": {
                "type": "agent_tool",
                "project_id": project_id,
                "agent_id": "alpha",
                "tool_name": "list_dir",
            },
            "request_schema": {"type": "object"},
            "response_schema": {"type": "object"},
        }
        reg = client.post("/hermes/register", json={"project_id": project_id, "spec": spec})
        assert reg.status_code == 400
        detail = reg.json().get("detail", {})
        assert detail.get("code") == "HERMES_AGENT_TOOL_DISABLED"
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
