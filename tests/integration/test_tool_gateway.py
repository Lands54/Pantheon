from pathlib import Path

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


def test_tool_gateway_send_and_check_inbox_roundtrip():
    project_id = "test_tool_gateway_world"
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
                "message": "hello from gateway",
                "project_id": project_id,
            },
        )
        assert send_res.status_code == 200
        assert "Revelation sent" in send_res.json()["result"]

        inbox_res = client.post(
            "/tool-gateway/check_inbox",
            json={"agent_id": "receiver", "project_id": project_id},
        )
        assert inbox_res.status_code == 200
        msgs = inbox_res.json().get("messages", [])
        assert isinstance(msgs, list)
        assert any(m.get("content") == "hello from gateway" for m in msgs)
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")


def test_tool_gateway_list_agents_and_record_protocol():
    project_id = "test_tool_gateway_world_2"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        _set_agent_tool_provider(project_id, True)
        client.post("/agents/create", json={"agent_id": "alpha", "directives": "# alpha"})

        list_res = client.get("/tool-gateway/list_agents", params={"project_id": project_id})
        assert list_res.status_code == 200
        assert "alpha" in list_res.json()["result"]

        proto_res = client.post(
            "/tool-gateway/record_protocol",
            json={
                "subject": "alpha",
                "topic": "io",
                "relation": "list_dir",
                "object": "storage",
                "clause": "use jsonl",
                "project_id": project_id,
            },
        )
        assert proto_res.status_code == 200
        assert "Protocol registered" in proto_res.json()["result"]

        registry_file = Path("projects") / project_id / "protocols" / "registry.json"
        assert registry_file.exists()
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
