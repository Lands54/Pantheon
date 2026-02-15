from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    cfg["projects"][project_id]["command_executor"] = "docker"
    cfg["projects"][project_id]["docker_enabled"] = True
    cfg["projects"][project_id]["detach_enabled"] = True
    client.post("/config/save", json=cfg)


def test_detach_submit_and_list(monkeypatch):
    project_id = "it_detach_submit_list"
    client.post("/projects/create", json={"id": project_id})
    try:
        _switch_project(project_id)
        monkeypatch.setattr("gods.runtime.detach.service.start_job", lambda *a, **k: True)

        submit_res = client.post(
            f"/projects/{project_id}/detach/submit",
            json={"agent_id": "genesis", "command": "echo hello"},
        )
        assert submit_res.status_code == 200
        job_id = submit_res.json().get("job_id")
        assert job_id

        list_res = client.get(f"/projects/{project_id}/detach/jobs", params={"limit": 50})
        assert list_res.status_code == 200
        items = list_res.json().get("items", [])
        assert any(i.get("job_id") == job_id for i in items)
    finally:
        client.delete(f"/projects/{project_id}")

