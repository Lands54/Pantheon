import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server import app
from gods.config import runtime_config


client = TestClient(app)


def _docker_ready() -> bool:
    try:
        v = subprocess.run(["docker", "version"], capture_output=True, text=True, timeout=5)
        if v.returncode != 0:
            return False
        i = subprocess.run(["docker", "image", "inspect", "gods-agent-base:py311"], capture_output=True, text=True, timeout=5)
        return i.returncode == 0
    except Exception:
        return False


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


@pytest.mark.skipif(not _docker_ready(), reason="docker or gods-agent-base:py311 not available")
def test_docker_runtime_start_stop_lifecycle():
    project_id = "it_docker_start_stop"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        client.post("/agents/create", json={"agent_id": "ground", "directives": "# ground"})

        cfg = client.get("/config").json()
        proj = cfg["projects"][project_id]
        proj["active_agents"] = ["ground"]
        proj["command_executor"] = "docker"
        proj["docker_enabled"] = True
        proj["docker_image"] = "gods-agent-base:py311"
        client.post("/config/save", json=cfg)

        start_res = client.post(f"/projects/{project_id}/start")
        assert start_res.status_code == 200

        status = client.get(f"/projects/{project_id}/runtime/agents").json()
        rows = status.get("agents", [])
        assert rows
        assert rows[0]["agent_id"] == "ground"

        stop_res = client.post(f"/projects/{project_id}/stop")
        assert stop_res.status_code == 200
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
