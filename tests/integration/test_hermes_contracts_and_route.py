from __future__ import annotations

from fastapi.testclient import TestClient

from api.server import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_hermes_contract_resolve_and_route_http():
    project_id = "test_hermes_contract_route"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        contract = {
            "name": "eco.protocol",
            "version": "1.0.0",
            "submitter": "ground",
            "committers": ["grass"],
            "status": "active",
            "default_obligations": [
                {
                    "id": "sync_state",
                    "summary": "sync state",
                    "io": {
                        "request_schema": {"type": "object"},
                        "response_schema": {"type": "object"},
                    },
                    "runtime": {"mode": "sync", "timeout_sec": 10},
                }
            ],
            "obligations": {
                "grass": [
                    {
                        "id": "check_fire_speed",
                        "summary": "check fire speed",
                        "io": {
                            "request_schema": {"type": "object", "required": ["v"]},
                            "response_schema": {"type": "object"},
                        },
                        "runtime": {"mode": "sync", "timeout_sec": 10},
                    }
                ]
            },
        }
        reg = client.post("/hermes/contracts/register", json={"project_id": project_id, "contract": contract})
        assert reg.status_code == 200

        commit = client.post(
            "/hermes/contracts/commit",
            json={"project_id": project_id, "name": "eco.protocol", "version": "1.0.0", "agent_id": "tiger"},
        )
        assert commit.status_code == 200

        resolved = client.get(
            "/hermes/contracts/eco.protocol/1.0.0/resolved",
            params={"project_id": project_id},
        )
        assert resolved.status_code == 200
        data = resolved.json()["resolved"]
        assert "grass" in data["resolved_obligations"]
        assert "tiger" in data["resolved_obligations"]
        tiger_ids = [x.get("id") for x in data["resolved_obligations"]["tiger"]]
        assert "sync_state" in tiger_ids

        # Register route-able HTTP protocol for fire god check
        spec = {
            "name": "fire.check_speed",
            "version": "1.0.0",
            "description": "placeholder",
            "mode": "both",
            "owner_agent": "fire_god",
            "function_id": "check_fire_speed",
            "provider": {
                "type": "http",
                "project_id": project_id,
                "url": "http://127.0.0.1:1/unreachable",
                "method": "POST",
            },
            "request_schema": {"type": "object"},
            "response_schema": {"type": "object", "required": ["result", "status_code"], "properties": {"result": {}, "status_code": {"type": "integer"}}},
        }
        r = client.post("/hermes/register", json={"project_id": project_id, "spec": spec})
        assert r.status_code == 200

        routed = client.post(
            "/hermes/route",
            json={
                "project_id": project_id,
                "caller_id": "ground",
                "target_agent": "fire_god",
                "function_id": "check_fire_speed",
                "mode": "sync",
                "payload": {"v": 3},
            },
        )
        # route is resolved; invoke fails due to unreachable url, but must return Hermes error shape
        assert routed.status_code == 200
        assert routed.json().get("ok") is False
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
