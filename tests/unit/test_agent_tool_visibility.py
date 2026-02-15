from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def test_disabled_tools_are_hidden_and_blocked():
    project_id = "unit_tool_visibility"
    agent_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# tester\nhide disabled tools", encoding="utf-8")

    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=[agent_id],
        agent_settings={
            agent_id: AgentModelConfig(
                disabled_tools=["check_inbox", "send_message"],
            )
        },
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        visible_tool_names = [t.name for t in agent.get_tools()]

        assert "check_inbox" not in visible_tool_names
        assert "send_message" not in visible_tool_names
        assert "list_dir" in visible_tool_names

        blocked = agent.execute_tool("check_inbox", {})
        assert "Divine Restriction" in blocked
        assert "disabled for you" in blocked
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
