"""
Integration Tests for API Routes
"""
import pytest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data


def test_get_config():
    """Test GET /config endpoint."""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "current_project" in data
    assert "projects" in data
    assert "available_agents" in data


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


def test_project_start_stop_endpoints():
    """Test project lifecycle endpoints: start/stop."""
    test_project_id = "test_start_stop_world"
    client.post("/projects/create", json={"id": test_project_id})
    try:
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
