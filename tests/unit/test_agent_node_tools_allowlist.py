from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nnode tool allowlist test", encoding="utf-8")


def test_agent_get_tools_for_node_uses_tool_policies_allowlist():
    project_id = "unit_tool_policies_allow"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="node tools",
        active_agents=[agent_id],
        agent_settings={
            agent_id: AgentModelConfig(
                disabled_tools=[],
                tool_policies={"react_graph": {"global": ["list", "read"]}},
            )
        },
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        names = [t.name for t in agent.get_tools_for_node("llm_think")]
        assert "list" in names
        assert "read" in names
        assert "write_file" not in names
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_agent_execute_tool_blocked_by_tool_policies():
    project_id = "unit_tool_policies_block"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="node tools block",
        active_agents=[agent_id],
        agent_settings={
            agent_id: AgentModelConfig(
                disabled_tools=[],
                tool_policies={"react_graph": {"global": ["finalize"]}},
            )
        },
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        out = agent.execute_tool("list", {"path": "."}, node_name="dispatch_tools")
        assert "not allowed in node 'dispatch_tools'" in out
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_agent_get_tools_for_node_falls_back_to_project_tool_policies():
    project_id = "unit_tool_policies_project_default"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="node tools project default",
        active_agents=[agent_id],
        tool_policies={"react_graph": {"global": ["read"]}},
        agent_settings={
            agent_id: AgentModelConfig(
                disabled_tools=[],
            )
        },
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        names = [t.name for t in agent.get_tools_for_node("llm_think")]
        assert names == ["read"]
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_agent_tool_policies_strategy_phase_precedence():
    project_id = "unit_tool_policies_strategy_phase"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="tool policies strategy phase",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        tool_policies={
            "react_graph": {"global": ["list"]},
            "freeform": {"global": ["read"]},
        },
        agent_settings={
            agent_id: AgentModelConfig(
                disabled_tools=[],
                tool_policies={"react_graph": {"global": ["finalize"]}},
            )
        },
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        names_dispatch = [t.name for t in agent.get_tools_for_node("dispatch_tools")]
        assert names_dispatch == ["finalize"]
        names_think = [t.name for t in agent.get_tools_for_node("llm_think")]
        assert names_think == ["finalize"]
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
