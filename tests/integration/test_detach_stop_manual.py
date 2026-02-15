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


def test_detach_stop_manual(monkeypatch):
    project_id = "it_detach_stop"
    client.post("/projects/create", json={"id": project_id})
    try:
        _switch_project(project_id)
        monkeypatch.setattr("gods.runtime.detach.service.start_job", lambda *a, **k: True)
        submit_res = client.post(
            f"/projects/{project_id}/detach/submit",
            json={"agent_id": "genesis", "command": "echo hello"},
        )
        assert submit_res.status_code == 200
        job_id = submit_res.json()["job_id"]

        stop_res = client.post(f"/projects/{project_id}/detach/jobs/{job_id}/stop")
        assert stop_res.status_code == 200
        row = (stop_res.json() or {}).get("job", {})
        assert row.get("status") in {"stopping", "stopped"}
        assert row.get("stop_reason") in {"manual", ""}
    finally:
        client.delete(f"/projects/{project_id}")

