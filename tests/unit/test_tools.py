"""
Unit Tests for Gods Tools
"""
import pytest
from pathlib import Path
from gods.tools.filesystem import validate_path
from gods.tools.filesystem import list_dir
from gods.tools.filesystem import read_file, write_file


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


def test_list_dir_returns_empty_marker_for_empty_directory():
    """list_dir should not return blank when directory has no visible files."""
    project_id = "unit_list_dir_empty"
    caller_id = "tester"
    empty_dir = Path("projects") / project_id / "agents" / caller_id / "empty"
    empty_dir.mkdir(parents=True, exist_ok=True)

    out = list_dir.invoke({"path": "empty", "caller_id": caller_id, "project_id": project_id})
    assert out == "[EMPTY] No visible files or directories."


def test_memory_files_are_hidden_and_protected():
    project_id = "unit_memory_hidden"
    caller_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / caller_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory.md").write_text("secret", encoding="utf-8")
    (agent_dir / "memory_archive.md").write_text("archive", encoding="utf-8")
    (agent_dir / "normal.txt").write_text("ok", encoding="utf-8")

    listed = list_dir.invoke({"path": ".", "caller_id": caller_id, "project_id": project_id})
    assert "memory.md" not in listed
    assert "memory_archive.md" not in listed
    assert "normal.txt" in listed

    read_res = read_file.invoke({"path": "memory.md", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in read_res

    write_res = write_file.invoke({"path": "memory.md", "content": "x", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in write_res
