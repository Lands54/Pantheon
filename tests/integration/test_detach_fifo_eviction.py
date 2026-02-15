from __future__ import annotations

import time

from fastapi.testclient import TestClient

from api.server import app
from gods.runtime.detach.models import DetachStatus
from gods.runtime.detach.service import reconcile
from gods.runtime.detach.store import create_job, transition_job, update_job

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    p = cfg["projects"][project_id]
    p["command_executor"] = "docker"
    p["docker_enabled"] = True
    p["detach_enabled"] = True
    p["detach_max_running_per_project"] = 1
    p["detach_max_running_per_agent"] = 2
    client.post("/config/save", json=cfg)


def test_detach_fifo_eviction(monkeypatch):
    project_id = "it_detach_fifo"
    client.post("/projects/create", json={"id": project_id})
    try:
        _switch_project(project_id)
        victim_calls: list[tuple[str, str]] = []

        def _fake_stop(project_id: str, job_id: str, grace_sec: int, reason: str = "manual"):
            victim_calls.append((job_id, reason))
            transition_job(project_id, job_id, DetachStatus.STOPPED, stop_reason=reason, exit_code=137)
            return True

        monkeypatch.setattr("gods.runtime.detach.service.stop_job", _fake_stop)
        monkeypatch.setattr("gods.runtime.detach.service._max_running_project", lambda _pid: 1)
        monkeypatch.setattr("gods.runtime.detach.service._max_running_agent", lambda _pid: 2)
        monkeypatch.setattr("gods.runtime.detach.service._ttl", lambda _pid: 999999)

        j1 = create_job(project_id, "genesis", "echo j1")
        j2 = create_job(project_id, "genesis", "echo j2")
        transition_job(project_id, j1.job_id, DetachStatus.RUNNING)
        transition_job(project_id, j2.job_id, DetachStatus.RUNNING)
        now = time.time()
        update_job(project_id, j1.job_id, started_at=now - 2)
        update_job(project_id, j2.job_id, started_at=now - 1)

        res = reconcile(project_id)
        assert j1.job_id in res.get("evicted", [])
        assert (j1.job_id, "limit_fifo") in victim_calls
    finally:
        client.delete(f"/projects/{project_id}")
