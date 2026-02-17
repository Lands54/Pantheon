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
            "/events/submit",
            json={
                "project_id": project_id,
                "domain": "runtime",
                "event_type": "detach_submitted_event",
                "payload": {"agent_id": "genesis", "command": "echo hello"},
            },
        )
        assert submit_res.status_code == 200
        job_id = (submit_res.json().get("meta") or {}).get("job_id", "")
        assert job_id

        stop_res = client.post(
            "/events/submit",
            json={
                "project_id": project_id,
                "domain": "runtime",
                "event_type": "detach_stopping_event",
                "payload": {"job_id": job_id},
            },
        )
        assert stop_res.status_code == 200
        row = stop_res.json() or {}
        assert row.get("event_type") == "detach_stopping_event"
        assert row.get("state") in {"queued", "done"}
    finally:
        client.delete(f"/projects/{project_id}")
