from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config
from gods.iris import list_events, InboxMessageState


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

        res = client.post("/confess", json={"agent_id": "receiver", "title": "hello-title", "message": "hello", "silent": False})
        assert res.status_code == 200
        body = res.json()
        assert "inbox_event_id" in body

        inbox = [x.to_dict() for x in list_events(project_id=project_id, agent_id="receiver", state=InboxMessageState.PENDING, limit=50)]
        assert any(item.get("content") == "hello" for item in inbox)
        assert any(item.get("title") == "hello-title" for item in inbox)

        outbox_res = client.get(
            f"/projects/{project_id}/inbox/outbox",
            params={"from_agent_id": "High Overseer", "to_agent_id": "receiver", "limit": 50},
        )
        outbox_items = outbox_res.json().get("items", [])
        assert any(item.get("title") == "hello-title" for item in outbox_items)
        assert any(item.get("status") in {"pending", "delivered", "handled"} for item in outbox_items)

        pulse_event_id = str(body.get("pulse_event_id", "") or "").strip()
        if pulse_event_id:
            evt_res = client.get(
                "/angelia/events",
                params={"project_id": project_id, "agent_id": "receiver", "event_type": "inbox_event", "limit": 50},
            )
            items = evt_res.json().get("items", [])
            assert any(item.get("event_id") == pulse_event_id for item in items)
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
