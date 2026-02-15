from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_project_report_written_to_mnemosyne_human():
    project_id = "test_project_report_mnemo_world"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        build = client.post(f"/projects/{project_id}/report/build")
        assert build.status_code == 200
        entry_id = build.json().get("mnemosyne_entry_id")
        assert entry_id

        lst = client.get("/mnemosyne/list", params={"project_id": project_id, "vault": "human", "limit": 50})
        assert lst.status_code == 200
        entries = lst.json().get("entries", [])
        hit = next((x for x in entries if x.get("entry_id") == entry_id), None)
        assert hit is not None
        assert "project_report" in hit.get("tags", [])
        assert project_id in hit.get("tags", [])
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
