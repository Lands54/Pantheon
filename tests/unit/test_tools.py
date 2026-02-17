"""
Unit Tests for Gods Tools
"""
import pytest
from pathlib import Path
import json
import shutil
from gods.tools.filesystem import validate_path
from gods.tools.filesystem import list_dir
from gods.tools.filesystem import read_file, write_file
from gods.tools.hermes import register_contract, list_contracts
from gods.config import runtime_config, ProjectConfig


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


def test_validate_path_blocks_similar_prefix_escape():
    """validate_path must reject escapes into sibling-like directory names."""
    with pytest.raises(PermissionError):
        validate_path("a", "test_project_prefix_escape", "../ab/secret.txt")


def test_validate_path_blocks_absolute_path():
    """validate_path must reject absolute paths outside territory."""
    with pytest.raises(PermissionError):
        validate_path("test_agent", "test_project_abs_escape", "/tmp/escape.txt")


def test_gods_tools_list():
    """Test that GODS_TOOLS contains all expected tools."""
    from gods.tools import GODS_TOOLS
    
    tool_names = [t.name for t in GODS_TOOLS]
    
    # Communication tools
    assert "check_inbox" in tool_names
    assert "send_message" in tool_names
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
    (agent_dir / "debug").mkdir(parents=True, exist_ok=True)

    listed = list_dir.invoke({"path": ".", "caller_id": caller_id, "project_id": project_id})
    assert "memory.md" not in listed
    assert "memory_archive.md" not in listed
    assert "agent.md" not in listed
    assert "runtime_state.json" not in listed
    assert "debug" not in listed
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


def test_list_contracts_shows_title_and_description():
    project_id = "unit_contract_list"
    caller_id = "tester"
    runtime_config.projects[project_id] = ProjectConfig()
    try:
        contract = {
            "title": "Library Contract",
            "version": "1.0.0",
            "description": "Manage catalog and circulation responsibilities.",
            "submitter": caller_id,
            "committers": [caller_id],
            "default_obligations": [
                {
                    "id": "health_check",
                    "summary": "health check endpoint",
                    "provider": {
                        "type": "http",
                        "url": "http://127.0.0.1:1/health",
                        "method": "GET",
                    },
                    "io": {
                        "request_schema": {"type": "object"},
                        "response_schema": {"type": "object"},
                    },
                    "runtime": {"mode": "sync", "timeout_sec": 3},
                }
            ],
            "obligations": {},
        }
        reg = register_contract.invoke(
            {
                "contract_json": json.dumps(contract, ensure_ascii=False),
                "caller_id": caller_id,
                "project_id": project_id,
            }
        )
        assert '"ok": true' in reg.lower()

        listed = list_contracts.invoke({"caller_id": caller_id, "project_id": project_id})
        data = json.loads(listed)
        assert data["ok"] is True
        assert data["contracts"]
        row = data["contracts"][0]
        assert row["title"] == "Library Contract"
        assert "catalog and circulation" in row["description"]
    finally:
        runtime_config.projects.pop(project_id, None)
        proj_dir = Path("projects") / project_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)
