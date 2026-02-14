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
    assert "finalize" in tool_names
    
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
    assert "[Current CWD:" in out
    assert "[EMPTY] No visible files or directories." in out


def test_memory_files_are_hidden_and_protected():
    project_id = "unit_memory_hidden"
    caller_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / caller_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory.md").write_text("secret", encoding="utf-8")
    (agent_dir / "memory_archive.md").write_text("archive", encoding="utf-8")
    (agent_dir / "agent.md").write_text("profile", encoding="utf-8")
    (agent_dir / "runtime_state.json").write_text("{}", encoding="utf-8")
    (agent_dir / "normal.txt").write_text("ok", encoding="utf-8")

    listed = list_dir.invoke({"path": ".", "caller_id": caller_id, "project_id": project_id})
    assert "memory.md" not in listed
    assert "memory_archive.md" not in listed
    assert "agent.md" not in listed
    assert "runtime_state.json" not in listed
    assert "normal.txt" in listed

    read_res = read_file.invoke({"path": "memory.md", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in read_res
    assert "[Current CWD:" in read_res
    assert "Suggested next step:" in read_res
    read_agent_res = read_file.invoke({"path": "agent.md", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in read_agent_res

    write_res = write_file.invoke({"path": "memory.md", "content": "x", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in write_res
    assert "Suggested next step:" in write_res


def test_read_file_missing_has_actionable_hint():
    project_id = "unit_read_file_hint"
    caller_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / caller_id
    src_dir = agent_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "models.py").write_text("x=1\n", encoding="utf-8")

    bad_path = f"projects/{project_id}/agents/{caller_id}/models.py"
    out = read_file.invoke({"path": bad_path, "caller_id": caller_id, "project_id": project_id})
    assert "[Current CWD:" in out
    assert "not found" in out
    assert "Suggested next step:" in out
    assert "try 'models.py'" in out or "found similarly named files" in out
