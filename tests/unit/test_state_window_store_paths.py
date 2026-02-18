import json
import shutil
from pathlib import Path

from langchain_core.messages import HumanMessage

from gods.config import ProjectConfig, runtime_config
from gods.mnemosyne.facade import load_state_window, save_state_window
from gods.paths import runtime_state_window_path


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
