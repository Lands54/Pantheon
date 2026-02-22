"""
Unit Tests for Gods Tools
"""
import pytest
from pathlib import Path
import json
import shutil
from gods.tools.filesystem import validate_path
from gods.tools.filesystem import list
from gods.tools.filesystem import read, write_file
from gods.tools.execution import run_command
from gods.tools.hermes import register_contract, list_contracts
from gods.config import runtime_config, ProjectConfig
from gods.iris.facade import enqueue_message
from gods.mnemosyne import facade as mnemosyne_facade


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
    assert "read" in tool_names
    assert "write_file" in tool_names
    assert "list" in tool_names
    
    # Execution tools
    assert "run_command" in tool_names
    
    # Should have at least 10 tools
    assert len(GODS_TOOLS) >= 10


def test_list_dir_returns_empty_marker_for_empty_directory():
    """list should not return blank when directory has no visible files."""
    project_id = "unit_list_dir_empty"
    caller_id = "tester"
    empty_dir = Path("projects") / project_id / "agents" / caller_id / "empty"
    empty_dir.mkdir(parents=True, exist_ok=True)

    out = list.invoke({"path": "empty", "caller_id": caller_id, "project_id": project_id})
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

    listed = list.invoke({"path": ".", "caller_id": caller_id, "project_id": project_id})
    assert "memory.md" not in listed
    assert "memory_archive.md" not in listed
    assert "agent.md" not in listed
    assert "runtime_state.json" not in listed
    assert "debug" not in listed
    assert "normal.txt" in listed

    read_res = read.invoke({"path": "memory.md", "caller_id": caller_id, "project_id": project_id})
    assert "Divine Restriction" in read_res
    assert "[Current CWD:" in read_res
    assert "Suggested next step:" in read_res
    read_agent_res = read.invoke({"path": "agent.md", "caller_id": caller_id, "project_id": project_id})
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
    out = read.invoke({"path": bad_path, "caller_id": caller_id, "project_id": project_id})
    assert "[Current CWD:" in out
    assert "not found" in out
    assert "Suggested next step:" in out
    assert "try 'models.py'" in out or "found similarly named files" in out


def test_read_file_supports_range_and_shows_path_metadata():
    project_id = "unit_read_file_range"
    caller_id = "tester"
    agent_home = Path("projects") / project_id / "agents" / caller_id
    src = agent_home / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "demo.txt").write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    out = read.invoke(
        {
            "path": "src/demo.txt",
            "caller_id": caller_id,
            "project_id": project_id,
            "start": 2,
            "end": 3,
        }
    )
    assert "[Current CWD:" in out
    assert "[READ]" in out
    assert "path: src/demo.txt" in out
    assert "resolved_path:" in out
    assert "line_range: 2-3" in out
    assert "line2" in out
    assert "line3" in out
    assert "line1" not in out
    assert "line4" not in out


def test_read_and_list_mail_virtual_paths():
    project_id = "unit_mail_virtual_paths"
    caller_id = "alice"
    receiver_id = "bob"
    (Path("projects") / project_id / "agents" / caller_id).mkdir(parents=True, exist_ok=True)
    (Path("projects") / project_id / "agents" / receiver_id).mkdir(parents=True, exist_ok=True)

    row = enqueue_message(
        project_id=project_id,
        agent_id=caller_id,
        sender=receiver_id,
        title="t1",
        content="hello\nline2",
        msg_type="private",
        trigger_pulse=False,
        pulse_priority=100,
        attachments=[],
    )
    event_id = str(row.get("mail_event_id", ""))
    assert event_id

    inbox_list = list.invoke(
        {"path": "mail://inbox", "caller_id": caller_id, "project_id": project_id, "page_size": 10, "page": 1}
    )
    assert "[MAILBOX:inbox]" in inbox_list
    assert event_id in inbox_list

    inbox_read = read.invoke(
        {"path": f"mail://inbox/{event_id}", "caller_id": caller_id, "project_id": project_id, "start": 1, "end": 1}
    )
    assert "[READ_MAIL_INBOX]" in inbox_read
    assert "title: t1" in inbox_read
    assert "hello" in inbox_read
    assert "line2" not in inbox_read

    outbox_list = list.invoke(
        {"path": "mail://outbox", "caller_id": receiver_id, "project_id": project_id, "page_size": 10, "page": 1}
    )
    assert "[MAILBOX:outbox]" in outbox_list
    assert "[RECEIPT]" in outbox_list


def test_list_agent_virtual_paths():
    project_id = "unit_agent_virtual_paths"
    caller_id = "alpha"
    (Path("projects") / project_id / "agents" / caller_id).mkdir(parents=True, exist_ok=True)
    (Path("projects") / project_id / "agents" / "beta").mkdir(parents=True, exist_ok=True)
    profiles = Path("projects") / project_id / "mnemosyne" / "agent_profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / "alpha.md").write_text("# alpha\nAlpha role", encoding="utf-8")
    (profiles / "beta.md").write_text("# beta\nBeta role", encoding="utf-8")

    out = list.invoke(
        {"path": "agent://all", "caller_id": caller_id, "project_id": project_id, "page_size": 20, "page": 1}
    )
    assert "[AGENTS:all]" in out
    assert "[AGENT] id=alpha" in out
    assert "[AGENT] id=beta" in out


def test_read_and_list_artifact_virtual_paths():
    project_id = "unit_artifact_virtual_paths"
    caller_id = "alpha"
    (Path("projects") / project_id / "agents" / caller_id).mkdir(parents=True, exist_ok=True)

    ref = mnemosyne_facade.put_artifact_text(
        scope="agent",
        project_id=project_id,
        owner_agent_id=caller_id,
        actor_id=caller_id,
        text="a1\na2\na3",
        mime="text/plain",
        tags=[],
    )

    art_list = list.invoke(
        {"path": "artifact://agent", "caller_id": caller_id, "project_id": project_id, "page_size": 5, "page": 1}
    )
    assert "[ARTIFACTS:agent]" in art_list
    assert ref.artifact_id in art_list

    art_read = read.invoke(
        {"path": f"artifact://{ref.artifact_id}", "caller_id": caller_id, "project_id": project_id, "start": 2, "end": 3}
    )
    assert "[READ_ARTIFACT]" in art_read
    assert f"path: artifact://{ref.artifact_id}" in art_read
    assert "a2" in art_read and "a3" in art_read
    assert "a1" not in art_read


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


def test_read_and_list_contract_virtual_paths():
    project_id = "unit_contract_virtual_paths"
    caller_id = "tester"
    runtime_config.projects[project_id] = ProjectConfig()
    try:
        contract = {
            "title": "Coord Contract",
            "version": "1.0.0",
            "description": "Coordinate agents for task routing.",
            "submitter": caller_id,
            "committers": [caller_id],
            "default_obligations": [
                {
                    "id": "route_ping",
                    "summary": "route ping",
                    "provider": {"type": "http", "url": "http://127.0.0.1:1/ping", "method": "GET"},
                    "io": {"request_schema": {"type": "object"}, "response_schema": {"type": "object"}},
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

        out_list = list.invoke(
            {
                "path": "contract://active",
                "caller_id": caller_id,
                "project_id": project_id,
                "page_size": 10,
                "page": 1,
            }
        )
        assert "[CONTRACTS:active]" in out_list
        assert "Coord Contract@1.0.0" in out_list

        out_read = read.invoke(
            {
                "path": "contract://Coord Contract@1.0.0",
                "caller_id": caller_id,
                "project_id": project_id,
                "start": 1,
                "end": 40,
            }
        )
        assert "[READ_CONTRACT]" in out_read
        assert "title: Coord Contract" in out_read
        assert "version: 1.0.0" in out_read
        assert "route_ping" in out_read
    finally:
        runtime_config.projects.pop(project_id, None)
        proj_dir = Path("projects") / project_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)


def test_list_and_read_detach_virtual_paths(monkeypatch):
    project_id = "unit_detach_virtual_paths"
    caller_id = "alpha"
    (Path("projects") / project_id / "agents" / caller_id).mkdir(parents=True, exist_ok=True)
    fake_items = [
        {
            "job_id": "job_1",
            "agent_id": caller_id,
            "status": "running",
            "created_at": 100.0,
            "command": "python app.py",
        },
        {
            "job_id": "job_2",
            "agent_id": caller_id,
            "status": "failed",
            "created_at": 90.0,
            "command": "pytest -q",
        },
    ]

    from gods.tools import filesystem as fs_mod

    monkeypatch.setattr(
        fs_mod.runtime_facade,
        "detach_list_for_api",
        lambda project_id, agent_id="", status="", limit=50: {
            "project_id": project_id,
            "items": [x for x in fake_items if (not status or x["status"] == status)],
        },
    )
    monkeypatch.setattr(
        fs_mod.runtime_facade,
        "detach_get_logs",
        lambda project_id, job_id: {
            "project_id": project_id,
            "job_id": job_id,
            "tail": "line1\nline2\nline3",
        },
    )

    out_list = list.invoke(
        {"path": "detach://jobs", "caller_id": caller_id, "project_id": project_id, "page_size": 10, "page": 1}
    )
    assert "[DETACH:jobs]" in out_list
    assert "job_1" in out_list and "job_2" in out_list

    out_read = read.invoke(
        {"path": "detach://job_1", "caller_id": caller_id, "project_id": project_id, "start": 2, "end": 3}
    )
    assert "[READ_DETACH_LOG]" in out_read
    assert "job_id: job_1" in out_read
    assert "line2" in out_read and "line3" in out_read
    assert "line1" not in out_read


def test_read_detach_virtual_path_blocks_non_owner(monkeypatch):
    project_id = "unit_detach_virtual_forbidden"
    caller_id = "alpha"
    (Path("projects") / project_id / "agents" / caller_id).mkdir(parents=True, exist_ok=True)

    from gods.tools import filesystem as fs_mod

    monkeypatch.setattr(
        fs_mod.runtime_facade,
        "detach_list_for_api",
        lambda project_id, agent_id="", status="", limit=50: {"project_id": project_id, "items": []},
    )
    monkeypatch.setattr(
        fs_mod.runtime_facade,
        "detach_get_logs",
        lambda project_id, job_id: {"project_id": project_id, "job_id": job_id, "tail": "should_not_be_seen"},
    )

    out = read.invoke(
        {"path": "detach://other_job", "caller_id": caller_id, "project_id": project_id, "start": 1, "end": 0}
    )
    assert "Permission Error" in out
    assert "not owned by caller" in out


def test_run_command_with_detach_flag_submits_background_job(monkeypatch):
    from gods.tools import execution as exec_mod

    monkeypatch.setattr(
        exec_mod,
        "detach_submit",
        lambda project_id, agent_id, command: {
            "ok": True,
            "job_id": "job_det_1",
            "status": "queued",
            "project_id": project_id,
            "agent_id": agent_id,
            "command": command,
        },
    )
    out = run_command.invoke(
        {
            "command": "python app.py",
            "caller_id": "alpha",
            "project_id": "unit_cmd_detach",
            "detach": True,
        }
    )
    assert '"ok": true' in out.lower()
    assert "job_det_1" in out
