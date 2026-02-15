from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_hermes_ports_api_reserve_release():
    project_id = "test_hermes_ports_api"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        reserve = client.post(
            "/hermes/ports/reserve",
            json={"project_id": project_id, "owner_id": "ground", "min_port": 15200, "max_port": 15300, "note": "ground service"},
        )
        assert reserve.status_code == 200
        lease = reserve.json().get("lease", {})
        assert int(lease.get("port", 0)) >= 15200

        listing = client.get("/hermes/ports/list", params={"project_id": project_id})
        assert listing.status_code == 200
        assert any(x.get("owner_id") == "ground" for x in listing.json().get("leases", []))

        release = client.post(
            "/hermes/ports/release",
            json={"project_id": project_id, "owner_id": "ground", "port": int(lease["port"])},
        )
        assert release.status_code == 200
        assert int(release.json().get("released", 0)) == 1
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
