from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config


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

        res = client.post("/confess", json={"agent_id": "receiver", "message": "hello", "silent": False})
        assert res.status_code == 200
        body = res.json()
        assert "inbox_event_id" in body

        inbox_res = client.get(
            f"/projects/{project_id}/inbox/events",
            params={"agent_id": "receiver", "state": "pending", "limit": 50},
        )
        inbox = inbox_res.json().get("items", [])
        assert any(item.get("content") == "hello" for item in inbox)

        pulse_res = client.get(
            f"/projects/{project_id}/pulse/queue",
            params={"agent_id": "receiver", "status": "queued", "limit": 50},
        )
        queued = pulse_res.json().get("items", [])
        assert any(item.get("event_type") == "inbox_event" for item in queued)
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
