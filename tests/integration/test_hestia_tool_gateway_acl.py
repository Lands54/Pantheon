from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_hestia_blocks_tool_gateway_send_message_when_edge_disabled():
    project_id = "it_hestia_gateway_acl"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "sender", "directives": "# sender"})
        client.post("/agents/create", json={"agent_id": "receiver", "directives": "# receiver"})

        edge_res = client.post(
            "/hestia/edge",
            json={
                "project_id": project_id,
                "from_id": "sender",
                "to_id": "receiver",
                "allowed": False,
            },
        )
        assert edge_res.status_code == 200

        send_res = client.post(
            "/tool-gateway/send_message",
            json={
                "from_id": "sender",
                "to_id": "receiver",
                "title": "blocked",
                "message": "should be blocked",
                "project_id": project_id,
            },
        )
        assert send_res.status_code == 403
        assert "social graph denies route" in send_res.json().get("detail", "")
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
