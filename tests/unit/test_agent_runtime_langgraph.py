from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


class _FakeBrain:
    def __init__(self):
        self.calls = 0

    def think_with_tools(self, messages, tools, trace_meta=None):
        if self.calls == 0:
            self.calls += 1
            return AIMessage(
                content="first action",
                tool_calls=[
                    {"id": "t1", "name": "list_dir", "args": {"path": "."}},
                ],
            )
        self.calls += 1
        return AIMessage(content="done", tool_calls=[])


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nlanggraph runtime test", encoding="utf-8")


def test_langgraph_react_graph_finish_continue_paths():
    project_id = "unit_langgraph_react"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="unit react",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
        phase_strategy="react_graph",
        tool_loop_max=3,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        agent.brain = _FakeBrain()
        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="start", name="tester")],
            "context": "react run",
            "next_step": "",
        }
        out = agent.process(state)
        assert out["next_step"] == "finish"
        mem_text = (Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}.md").read_text(encoding="utf-8")
        assert "[[ACTION]] list_dir" in mem_text
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_langgraph_freeform_graph_paths():
    project_id = "unit_langgraph_freeform"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="unit freeform",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[], phase_strategy="freeform")},
        simulation_enabled=False,
        phase_strategy="react_graph",
        tool_loop_max=3,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        agent.brain = _FakeBrain()
        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="start", name="tester")],
            "context": "freeform run",
            "next_step": "",
        }
        out = agent.process(state)
        assert out["next_step"] == "finish"
        runtime_text = (Path("projects") / project_id / "mnemosyne" / "runtime_events" / f"{agent_id}.jsonl").read_text(
            encoding="utf-8"
        )
        assert "agent.mode.freeform" in runtime_text
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
