from __future__ import annotations

from fastapi.testclient import TestClient

from api.server import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_hermes_contract_commit_snapshot_and_route_http():
    project_id = "test_hermes_contract_route"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        contract = {
            "version": "1.0.0",
            "title": "Ecosystem Contract",
            "description": "Defines cross-agent ecosystem obligations and runtime clauses.",
            "submitter": "ground",
            "committers": ["grass", "tiger"],
            "status": "active",
            "default_obligations": [
                {
                    "id": "sync_state",
                    "summary": "sync state",
                    "provider": {
                        "type": "http",
                        "url": "http://127.0.0.1:1/sync_state",
                        "method": "POST",
                    },
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
                        "provider": {
                            "type": "http",
                            "url": "http://127.0.0.1:1/check_fire_speed",
                            "method": "POST",
                        },
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
        assert reg.json()["contract"]["committers"] == ["ground"]
        assert reg.json()["contract"]["missing_committers"] == ["grass", "tiger"]

        commit_grass = client.post(
            "/hermes/contracts/commit",
            json={"project_id": project_id, "title": "Ecosystem Contract", "version": "1.0.0", "agent_id": "grass"},
        )
        assert commit_grass.status_code == 200
        assert commit_grass.json()["contract"]["missing_committers"] == ["tiger"]

        commit = client.post(
            "/hermes/contracts/commit",
            json={"project_id": project_id, "title": "Ecosystem Contract", "version": "1.0.0", "agent_id": "tiger"},
        )
        assert commit.status_code == 200
        assert commit.json()["contract"]["is_fully_committed"] is True
        assert commit.json()["contract"]["missing_committers"] == []

        listed_after_commit = client.get(
            "/hermes/contracts/list",
            params={"project_id": project_id},
        )
        assert listed_after_commit.status_code == 200
        data = listed_after_commit.json()["contracts"][0]
        assert data["title"] == "Ecosystem Contract"
        assert data["is_fully_committed"] is True
        assert data["missing_committers"] == []

        disable_tiger = client.post(
            "/hermes/contracts/disable",
            json={
                "project_id": project_id,
                "title": "Ecosystem Contract",
                "version": "1.0.0",
                "agent_id": "tiger",
                "reason": "handoff",
            },
        )
        assert disable_tiger.status_code == 200

        # Remove all committers; contract becomes disabled.
        for agent in ("grass", "ground"):
            r = client.post(
                "/hermes/contracts/disable",
                json={
                    "project_id": project_id,
                    "title": "Ecosystem Contract",
                    "version": "1.0.0",
                    "agent_id": agent,
                    "reason": "close",
                },
            )
            assert r.status_code == 200

        commit_disabled = client.post(
            "/hermes/contracts/commit",
            json={"project_id": project_id, "title": "Ecosystem Contract", "version": "1.0.0", "agent_id": "wolf"},
        )
        assert commit_disabled.status_code == 400

        listed_default = client.get("/hermes/contracts/list", params={"project_id": project_id})
        assert listed_default.status_code == 200
        assert listed_default.json()["contracts"] == []

        listed_all = client.get(
            "/hermes/contracts/list",
            params={"project_id": project_id, "include_disabled": True},
        )
        assert listed_all.status_code == 200
        assert listed_all.json()["contracts"]

        # Register route-able HTTP protocol for fire god check
        spec = {
            "name": "fire.check_speed",
            "description": "placeholder",
            "mode": "both",
            "owner_agent": "fire_god",
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
                    "function_id": "check_speed",
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
