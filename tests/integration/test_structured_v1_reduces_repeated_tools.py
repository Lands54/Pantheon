from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


class _CaptureBrain:
    def __init__(self):
        self.last_recent_count = 0

    def think_with_tools(self, messages, tools, trace_meta=None):
        self.last_recent_count = max(0, len(messages) - 1)
        return AIMessage(content="done", tool_calls=[])


def test_structured_v1_recent_messages_not_fixed_eight():
    project_id = "it_structured_recent_window"
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
        context_recent_message_limit=40,
        context_budget_recent_messages=30000,
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        brain = _CaptureBrain()
        agent.brain = brain
        msgs = [HumanMessage(content=f"m{i}-" + ("x" * 20), name="h") for i in range(30)]
        state = {
            "project_id": project_id,
            "messages": msgs,
            "context": "objective",
            "next_step": "",
        }
        agent.process(state)
        assert brain.last_recent_count > 8
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
