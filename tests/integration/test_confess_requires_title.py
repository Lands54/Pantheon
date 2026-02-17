from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_no_confess_route():
    project_id = "it_no_confess_route"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "receiver", "directives": "# receiver"})

        res = client.post("/confess", json={"agent_id": "receiver", "message": "hello", "silent": True})
        assert res.status_code in (404, 405)
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")


def test_interaction_message_requires_title():
    project_id = "it_interaction_requires_title"
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
                    "sender_id": "human.overseer",
                    "content": "hello",
                    "msg_type": "confession",
                    "trigger_pulse": False,
                },
            },
        )
        assert res.status_code == 400
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
