from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods import events as events_bus
from gods.config import runtime_config


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_message_flow_no_interaction_agent_trigger_event_created():
    project_id = "it_no_trigger_from_message"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "sender", "directives": "# sender"})
        client.post("/agents/create", json={"agent_id": "receiver", "directives": "# receiver"})

        send_res = client.post(
            "/tool-gateway/send_message",
            json={
                "from_id": "sender",
                "to_id": "receiver",
                "title": "hello",
                "message": "world",
                "project_id": project_id,
            },
        )
        assert send_res.status_code == 200

        rows = events_bus.list_events(project_id, limit=500)
        etypes = [str(x.event_type) for x in rows]
        assert "interaction.message.sent" in etypes
        assert "mail_event" in etypes
        assert "interaction.agent.trigger" not in etypes
        interaction_rows = [x for x in rows if str(x.domain) == "interaction"]
        assert interaction_rows
        assert all(str(x.state.value) != "queued" for x in interaction_rows)
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")


def test_event_submit_rejects_interaction_agent_trigger():
    project_id = "it_trigger_reject"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "alpha", "directives": "# alpha"})

        res = client.post(
            "/events/submit",
            json={
                "project_id": project_id,
                "domain": "interaction",
                "event_type": "interaction.agent.trigger",
                "payload": {"agent_id": "alpha", "reason": "test"},
            },
        )
        assert res.status_code == 410

        res2 = client.post(
            "/events/submit",
            json={
                "project_id": project_id,
                "domain": "interaction",
                "event_type": "interaction.unknown.xxx",
                "payload": {"agent_id": "alpha"},
            },
        )
        assert res2.status_code == 400
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
