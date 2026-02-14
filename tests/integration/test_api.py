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
