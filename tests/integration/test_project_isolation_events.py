from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_project_event_isolation():
    p1 = "it_iso_p1"
    p2 = "it_iso_p2"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": p1})
        client.post("/projects/create", json={"id": p2})

        _switch_project(p1)
        client.post("/agents/create", json={"agent_id": "x", "directives": "# x"})
        client.post(
            "/events/submit",
            json={
                "project_id": p1,
                "domain": "interaction",
                "event_type": "interaction.message.sent",
                "payload": {
                    "to_id": "x",
                    "sender_id": "human.overseer",
                    "title": "m1-title",
                    "content": "m1",
                    "msg_type": "confession",
                    "trigger_pulse": False,
                },
            },
        )

        p1_rows = client.get(
            "/events",
            params={"project_id": p1, "domain": "iris", "agent_id": "x", "event_type": "mail_event", "limit": 50},
        ).json().get("items", [])
        assert len(p1_rows) >= 1

        p2_rows = client.get(
            "/events",
            params={"project_id": p2, "domain": "iris", "agent_id": "x", "event_type": "mail_event", "limit": 50},
        ).json().get("items", [])
        assert p2_rows == []
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{p1}")
        client.delete(f"/projects/{p2}")
