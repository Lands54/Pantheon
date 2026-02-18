from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config
from gods.mnemosyne import facade as mnemosyne_facade


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_tool_gateway_send_message_with_attachments():
    project_id = "it_tool_gateway_att"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "sender", "directives": "# sender"})
        client.post("/agents/create", json={"agent_id": "receiver", "directives": "# receiver"})
        ref = mnemosyne_facade.put_artifact_text(
            scope="agent",
            project_id=project_id,
            owner_agent_id="sender",
            actor_id="sender",
            text='{"x":1}',
            mime="application/json",
            tags=[],
        )
        send_res = client.post(
            "/tool-gateway/send_message",
            json={
                "from_id": "sender",
                "to_id": "receiver",
                "title": "gateway-title",
                "message": "hello with attachment",
                "attachments": [ref.artifact_id],
                "project_id": project_id,
            },
        )
        assert send_res.status_code == 200
        assert send_res.json().get("attachments_count") == 1

        inbox_res = client.post(
            "/tool-gateway/check_inbox",
            json={"agent_id": "receiver", "project_id": project_id},
        )
        assert inbox_res.status_code == 200
        msgs = inbox_res.json().get("messages", [])
        assert msgs and msgs[0].get("attachments_count", 0) >= 1
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
