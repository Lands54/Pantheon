from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_check_inbox_disabled_by_default_for_new_agent():
    project_id = "it_check_inbox_default_disabled"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "a", "directives": "# a"})

        cfg = client.get("/config").json()
        disabled = cfg["projects"][project_id]["agent_settings"]["a"].get("disabled_tools", [])
        assert "check_inbox" in disabled
        assert "check_outbox" in disabled
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
