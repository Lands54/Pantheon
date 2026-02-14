"""
Unit Tests for Gods Core Configuration
"""
import pytest
import json
from pathlib import Path
from gods.config import SystemConfig, ProjectConfig, AgentModelConfig


def test_agent_model_config_defaults():
    """Test AgentModelConfig default values."""
    config = AgentModelConfig()
    assert config.model == "google/gemini-2.0-flash-exp:free"
    assert config.disabled_tools == []


def test_project_config_defaults():
    """Test ProjectConfig default values."""
    config = ProjectConfig()
    assert config.name is None
    assert config.active_agents == ["genesis"]
    assert "genesis" in config.agent_settings
    assert config.simulation_enabled is False
    assert config.simulation_interval_min == 10
    assert config.simulation_interval_max == 40


def test_project_config_custom():
    """Test ProjectConfig with custom values."""
    config = ProjectConfig(
        name="Test World",
        active_agents=["agent1", "agent2"],
        simulation_enabled=True
    )
    assert config.name == "Test World"
    assert len(config.active_agents) == 2
    assert config.simulation_enabled is True


def test_system_config_defaults():
    """Test SystemConfig default values."""
    config = SystemConfig()
    assert config.openrouter_api_key == ""
    assert config.current_project == "default"
    assert "default" in config.projects


def test_system_config_serialization():
    """Test SystemConfig can be serialized to JSON."""
    config = SystemConfig()
    config.openrouter_api_key = "test_key"
    
    # Convert to dict
    data = config.model_dump()
    assert data["openrouter_api_key"] == "test_key"
    assert "projects" in data
    assert "default" in data["projects"]


def test_get_available_agents(tmp_path):
    """Test get_available_agents function."""
    from gods.config import get_available_agents
    
    # Create test project structure
    test_project = tmp_path / "projects" / "test" / "agents"
    test_project.mkdir(parents=True)
    
    # Create some agent directories
    (test_project / "agent1").mkdir()
    (test_project / "agent2").mkdir()
    (test_project / ".hidden").mkdir()  # Should be ignored
    
    # Note: This test would need to mock the actual project path
    # For now, just test that the function exists and returns a list
    agents = get_available_agents()
    assert isinstance(agents, list)
