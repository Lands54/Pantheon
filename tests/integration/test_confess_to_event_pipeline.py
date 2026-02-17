from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config
from gods.identity import HUMAN_AGENT_ID


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_confess_to_event_pipeline():
    project_id = "it_confess_event"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "receiver", "directives": "# receiver"})

        res = client.post(
            "/events/submit",
            json={
                "project_id": project_id,
                "domain": "interaction",
                "event_type": "interaction.message.sent",
                "payload": {
                    "to_id": "receiver",
                    "sender_id": HUMAN_AGENT_ID,
                    "title": "hello-title",
                    "content": "hello",
                    "msg_type": "confession",
                    "trigger_pulse": True,
                },
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "event_id" in body

        outbox_res = client.get(
            f"/projects/{project_id}/inbox/outbox",
            params={"from_agent_id": HUMAN_AGENT_ID, "to_agent_id": "receiver", "limit": 50},
        )
        outbox_items = outbox_res.json().get("items", [])
        assert any(item.get("title") == "hello-title" for item in outbox_items)
        assert any(item.get("status") in {"pending", "delivered", "handled"} for item in outbox_items)

        event_id = str(body.get("event_id", "") or "").strip()
        assert event_id
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
