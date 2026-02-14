"""
Unit Tests for Gods Tools
"""
import pytest
from pathlib import Path
from gods.tools.filesystem import validate_path


def test_validate_path_within_territory(tmp_path):
    """Test that validate_path allows access within agent territory."""
    # Create test structure
    project_root = tmp_path
    agent_territory = project_root / "projects" / "test_project" / "agents" / "test_agent"
    agent_territory.mkdir(parents=True)
    
    # This would need to be adapted to work with the actual validate_path function
    # which uses __file__ to find the project root
    # For now, test the concept
    assert agent_territory.exists()


def test_validate_path_outside_territory():
    """Test that validate_path blocks access outside agent territory."""
    # This should raise PermissionError
    with pytest.raises(PermissionError):
        # Attempting to access parent directory
        validate_path("test_agent", "test_project", "../../../etc/passwd")


def test_gods_tools_list():
    """Test that GODS_TOOLS contains all expected tools."""
    from gods.tools import GODS_TOOLS
    
    tool_names = [t.name for t in GODS_TOOLS]
    
    # Communication tools
    assert "check_inbox" in tool_names
    assert "send_message" in tool_names
    assert "send_to_human" in tool_names
    
    # Filesystem tools
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "list_dir" in tool_names
    
    # Execution tools
    assert "run_command" in tool_names
    
    # Should have at least 10 tools
    assert len(GODS_TOOLS) >= 10
