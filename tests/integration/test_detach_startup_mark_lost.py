from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.runtime.facade import (
    DetachStatus,
    create_job,
    detach_startup_mark_lost,
    get_job,
    transition_job,
)

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    cfg["projects"][project_id]["command_executor"] = "docker"
    cfg["projects"][project_id]["docker_enabled"] = True
    cfg["projects"][project_id]["detach_enabled"] = True
    client.post("/config/save", json=cfg)


def test_detach_startup_mark_lost():
    project_id = "it_detach_startup_lost"
    client.post("/projects/create", json={"id": project_id})
    try:
        _switch_project(project_id)
        j1 = create_job(project_id, "genesis", "echo a")
        j2 = create_job(project_id, "genesis", "echo b")
        transition_job(project_id, j2.job_id, DetachStatus.RUNNING)

        changed = detach_startup_mark_lost(project_id)
        assert changed >= 2

        g1 = get_job(project_id, j1.job_id)
        g2 = get_job(project_id, j2.job_id)
        assert g1 is not None and g1.status == DetachStatus.LOST
        assert g2 is not None and g2.status == DetachStatus.LOST
        assert g1.stop_reason == "startup_lost"
        assert g2.stop_reason == "startup_lost"
    finally:
        client.delete(f"/projects/{project_id}")
