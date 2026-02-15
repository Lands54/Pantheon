from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.janus.journal import latest_context_report


class _FakeBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        return AIMessage(content="done", tool_calls=[])


def test_context_strategy_switch_project_and_agent_override():
    project_id = "it_context_strategy_switch"
    agent_id = "alpha"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# alpha", encoding="utf-8")

    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=[agent_id],
        context_strategy="structured_v1",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        agent.brain = _FakeBrain()
        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="start", name="h")],
            "context": "objective",
            "next_step": "",
        }
        agent.process(state)
        r1 = latest_context_report(project_id, agent_id)
        assert r1 is not None
        assert r1.get("strategy_used") == "structured_v1"

        runtime_config.projects[project_id].agent_settings[agent_id].context_strategy = "invalid_legacy_mode"
        state2 = {
            "project_id": project_id,
            "messages": [HumanMessage(content="again", name="h")],
            "context": "objective",
            "next_step": "",
        }
        agent.process(state2)
        r2 = latest_context_report(project_id, agent_id)
        assert r2 is not None
        assert r2.get("strategy_used") == "structured_v1"
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
