"""
Integration Tests for API Routes
"""
import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from api.app import app
from api.services import project_service

project_service_module = importlib.import_module("api.services.project_service")

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data


def test_events_catalog_contains_llm_flag():
    response = client.get("/events/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    items = data.get("items", [])
    row = next((x for x in items if x.get("event_type") == "interaction.message.sent"), None)
    assert row is not None
    assert row.get("feeds_llm") is False
    assert "description" in row


def test_get_config():
    """Test GET /config endpoint."""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "current_project" in data
    assert "projects" in data
    assert "available_agents" in data


def test_get_config_schema():
    response = client.get("/config/schema")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "scopes" in data
    assert "fields" in data
    assert "groups" in data
    assert "tool_options" in data
    assert "deprecations" in data


def test_get_config_audit():
    response = client.get("/config/audit")
    assert response.status_code == 200
    data = response.json()
    assert "deprecated" in data
    assert "unreferenced" in data
    assert "naming_conflicts" in data


def test_list_projects():
    """Test GET /projects endpoint."""
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert "current" in data


def test_create_project():
    """Test POST /projects/create endpoint."""
    test_project_id = "test_integration_world"
    
    # Create project
    response = client.post(
        "/projects/create",
        json={"id": test_project_id}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify it exists
    response = client.get("/projects")
    data = response.json()
    assert test_project_id in data["projects"]
    proj = data["projects"][test_project_id]
    assert proj.get("active_agents", []) == []
    assert proj.get("agent_settings", {}) == {}
    # Verify layout scaffolded
    from pathlib import Path
    root = Path("projects") / test_project_id
    assert (root / "runtime" / "events.jsonl").exists()
    assert (root / "runtime" / "detach_jobs.jsonl").exists()
    assert (root / "runtime" / "locks").exists()
    assert (root / "mnemosyne" / "agent_profiles").exists()
    assert (root / "mnemosyne" / "memory_policy.json").exists()
    policy = (root / "mnemosyne" / "memory_policy.json").read_text(encoding="utf-8")
    assert "event.mail_event" in policy
    assert (root / "agents").exists()
    assert (root / "buffers").exists()
    
    # Cleanup
    client.delete(f"/projects/{test_project_id}")


def test_delete_project():
    """Test DELETE /projects/{project_id} endpoint."""
    test_project_id = "test_delete_world"
    
    # Create project first
    client.post("/projects/create", json={"id": test_project_id})
    
    # Delete it
    response = client.delete(f"/projects/{test_project_id}")
    assert response.status_code == 200
    
    # Verify it's gone
    response = client.get("/projects")
    data = response.json()
    assert test_project_id not in data["projects"]


def test_cannot_delete_default_project():
    """Test that default project cannot be deleted."""
    response = client.delete("/projects/default")
    assert response.status_code == 400


def test_rebuild_knowledge_graph():
    """Test POST /projects/{project_id}/knowledge/rebuild endpoint."""
    test_project_id = "test_graph_world"
    client.post("/projects/create", json={"id": test_project_id})
    try:
        response = client.post(f"/projects/{test_project_id}/knowledge/rebuild")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["project_id"] == test_project_id
        assert "output" in data
    finally:
        client.delete(f"/projects/{test_project_id}")




def test_create_agent_rejects_invalid_agent_id():
    response = client.post(
        "/agents/create",
        json={
            "agent_id": "Hign Overseer",
            "directives": "# Invalid"
        }
    )
    assert response.status_code == 400
    assert "invalid agent_id" in str(response.json().get("detail", ""))

def test_create_agent():
    """Test POST /agents/create endpoint."""
    response = client.post(
        "/agents/create",
        json={
            "agent_id": "test_agent",
            "directives": "# Test Agent\nYou are a test agent."
        }
    )
    assert response.status_code == 200
    
    # Cleanup
    client.delete("/agents/test_agent")


def test_delete_agent():
    """Test DELETE /agents/{agent_id} endpoint."""
    # Create agent first
    client.post(
        "/agents/create",
        json={
            "agent_id": "test_delete_agent",
            "directives": "# Test"
        }
    )
    
    # Delete it
    response = client.delete("/agents/test_delete_agent")
    assert response.status_code == 200


def test_get_agents_status():
    """Test GET /agents/status endpoint."""
    response = client.get("/agents/status")
    assert response.status_code == 200
    data = response.json()
    assert "project_id" in data
    assert "agents" in data


def test_removed_legacy_social_routes_not_exposed():
    """Legacy social routes are removed and must stay unavailable."""
    response = client.get("/prayers/check")
    assert response.status_code == 404


def test_project_start_stop_endpoints():
    """Test project lifecycle endpoints: start/stop."""
    test_project_id = "test_start_stop_world"
    client.post("/projects/create", json={"id": test_project_id})
    try:
        # Keep this test independent from host docker runtime availability.
        cfg = client.get("/config").json()
        cfg["projects"][test_project_id]["command_executor"] = "local"
        cfg["projects"][test_project_id]["docker_enabled"] = False
        client.post("/config/save", json=cfg)

        # Start target project (exclusive)
        response = client.post(f"/projects/{test_project_id}/start")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["project_id"] == test_project_id
        assert payload["simulation_enabled"] is True
        assert payload["current_project"] == test_project_id

        # Verify config state
        cfg = client.get("/config").json()
        assert cfg["current_project"] == test_project_id
        assert cfg["projects"][test_project_id]["simulation_enabled"] is True
        for pid, proj in cfg["projects"].items():
            if pid != test_project_id:
                assert proj["simulation_enabled"] is False

        # Stop target project
        response = client.post(f"/projects/{test_project_id}/stop")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["project_id"] == test_project_id
        assert payload["simulation_enabled"] is False
    finally:
        client.delete(f"/projects/{test_project_id}")


def test_project_start_fails_when_docker_unavailable(monkeypatch):
    """When project requires docker runtime and docker is unavailable, start should fail and keep simulation off."""
    test_project_id = "test_start_docker_unavailable"
    client.post("/projects/create", json={"id": test_project_id})
    try:
        cfg = client.get("/config").json()
        cfg["projects"][test_project_id]["command_executor"] = "docker"
        cfg["projects"][test_project_id]["docker_enabled"] = True
        client.post("/config/save", json=cfg)

        monkeypatch.setattr(project_service_module.runtime_facade, "docker_available", lambda: (False, "docker daemon down"))

        response = client.post(f"/projects/{test_project_id}/start")
        assert response.status_code == 503
        assert "Docker unavailable" in response.json().get("detail", "")
        cfg2 = client.get("/config").json()
        assert cfg2["projects"][test_project_id]["simulation_enabled"] is False
    finally:
        client.delete(f"/projects/{test_project_id}")


def test_mnemosyne_templates_roundtrip():
    test_project_id = "test_templates_world"
    client.post("/projects/create", json={"id": test_project_id})
    try:
        res = client.get("/mnemosyne/templates", params={"project_id": test_project_id})
        assert res.status_code == 200
        payload = res.json()
        assert "runtime_log" in payload
        assert "chronicle" in payload
        assert "llm_context" in payload

        put = client.put(
            "/mnemosyne/templates/runtime_log/memory_custom_case",
            json={"project_id": test_project_id, "template": "[CUSTOM] $agent_id -> $intent_key"},
        )
        assert put.status_code == 200
        row = put.json()
        assert row["scope"] == "runtime_log"
        assert row["key"] == "memory_custom_case"

        res2 = client.get("/mnemosyne/templates", params={"project_id": test_project_id})
        assert res2.status_code == 200
        payload2 = res2.json()
        assert payload2["runtime_log"]["memory_custom_case"] == "[CUSTOM] $agent_id -> $intent_key"

        pol = client.get("/mnemosyne/memory-policy", params={"project_id": test_project_id})
        assert pol.status_code == 200
        assert "llm.response" in pol.json().get("items", {})

        up_pol = client.put(
            "/mnemosyne/memory-policy/llm.response",
            json={
                "project_id": test_project_id,
                "to_chronicle": True,
                "chronicle_template_key": "memory_llm_response",
                "to_runtime_log": True,
                "runtime_log_template_key": "memory_custom_case",
            },
        )
        assert up_pol.status_code == 200
        assert up_pol.json()["runtime_log_template_key"] == "memory_custom_case"

        up_pol_ctx = client.put(
            "/mnemosyne/memory-policy/llm.response",
            json={
                "project_id": test_project_id,
                "to_llm_context": True,
                "llm_context_template_key": "memory_tool_error",
            },
        )
        assert up_pol_ctx.status_code == 200
        assert up_pol_ctx.json()["to_llm_context"] is True
        assert up_pol_ctx.json()["llm_context_template_key"] == "memory_tool_error"

        vars_res = client.get(
            "/mnemosyne/template-vars",
            params={"project_id": test_project_id, "intent_key": "llm.response"},
        )
        assert vars_res.status_code == 200
        vars_payload = vars_res.json()
        assert "content" in vars_payload.get("guaranteed_vars", [])
        assert "project_id" in vars_payload.get("guaranteed_vars", [])
    finally:
        client.delete(f"/projects/{test_project_id}")


def test_context_llm_latest_endpoint():
    test_project_id = "test_context_llm_latest_world"
    agent_id = "genesis"
    client.post("/projects/create", json={"id": test_project_id})
    try:
        # No trace file yet.
        r0 = client.get(f"/projects/{test_project_id}/context/llm-latest", params={"agent_id": agent_id})
        assert r0.status_code == 200
        d0 = r0.json()
        assert d0["available"] is False
        assert d0["trace"] is None

        trace_dir = Path("projects") / test_project_id / "runtime" / "debug" / agent_id
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / "llm_io.jsonl"
        row = {
            "ts": 1234567.0,
            "project_id": test_project_id,
            "agent_id": agent_id,
            "mode": "tools",
            "model": "unit-test-model",
            "request_messages": [{"type": "HumanMessage", "content": "# Hello\n**world**"}],
        }
        trace_file.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

        r1 = client.get(f"/projects/{test_project_id}/context/llm-latest", params={"agent_id": agent_id})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["available"] is True
        assert d1["trace"]["model"] == "unit-test-model"
        assert d1["trace"]["request_messages"][0]["content"] == "# Hello\n**world**"
    finally:
        client.delete(f"/projects/{test_project_id}")
