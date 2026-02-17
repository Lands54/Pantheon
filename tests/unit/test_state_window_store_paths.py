import json
import shutil
from pathlib import Path

from langchain_core.messages import HumanMessage

from gods.agents.state_window_store import load_state_window, save_state_window
from gods.config import ProjectConfig, runtime_config
from gods.paths import legacy_agent_state_window_path, runtime_state_window_path


def test_state_window_persists_under_runtime_dir():
    project_id = "unit_state_window_runtime_path"
    agent_id = "tester"
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="state-window",
        active_agents=[agent_id],
        context_state_window_limit=50,
    )
    try:
        save_state_window(project_id, agent_id, [HumanMessage(content="hello")])
        p = runtime_state_window_path(project_id, agent_id)
        assert p.exists()
        payload = json.loads(p.read_text(encoding="utf-8"))
        assert payload["project_id"] == project_id
        assert payload["agent_id"] == agent_id
        assert len(payload["messages"]) == 1
    finally:
        runtime_config.projects = old_projects
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_state_window_load_migrates_legacy_path():
    project_id = "unit_state_window_legacy_migrate"
    agent_id = "tester"
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="state-window-legacy",
        active_agents=[agent_id],
        context_state_window_limit=50,
    )
    try:
        legacy = legacy_agent_state_window_path(project_id, agent_id)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps(
                {
                    "project_id": project_id,
                    "agent_id": agent_id,
                    "limit": 50,
                    "messages": [{"type": "human", "data": {"content": "legacy"}}],
                }
            ),
            encoding="utf-8",
        )
        msgs = load_state_window(project_id, agent_id)
        assert [getattr(m, "content", "") for m in msgs] == ["legacy"]
        assert runtime_state_window_path(project_id, agent_id).exists()
        assert not legacy.exists()
    finally:
        runtime_config.projects = old_projects
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
