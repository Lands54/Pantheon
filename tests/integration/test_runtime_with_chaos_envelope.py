from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


class _NoopBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        return AIMessage(content="done", tool_calls=[])


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos runtime test", encoding="utf-8")


def test_runtime_injects_chaos_envelope():
    project_id = "it_chaos_runtime"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it chaos runtime",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
        phase_strategy="react_graph",
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        agent.brain = _NoopBrain()
        out = agent.process(
            {
                "project_id": project_id,
                "messages": [HumanMessage(content="run")],
                "mailbox": [],
                "triggers": [],
            }
        )
        env_metis = out.get("__metis_envelope")
        assert env_metis is not None
        assert getattr(env_metis, "strategy", "") == "react_graph"
        assert getattr(env_metis, "resource_snapshot", None) is not None
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
