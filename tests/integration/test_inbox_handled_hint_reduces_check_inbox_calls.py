from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.inbox.service import enqueue_message
from gods.pulse.scheduler_hooks import inject_inbox_before_pulse


class _CaptureBrain:
    def __init__(self):
        self.seen = ""

    def think_with_tools(self, messages, tools, trace_meta=None):
        self.seen = "\n".join([str(getattr(m, "content", "")) for m in messages])
        return AIMessage(content="done", tool_calls=[])


def test_inbox_context_contains_handled_semantics_for_agent_confidence():
    project_id = "it_inbox_handled_hint"
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
        context_budget_recent_messages=20000,
        context_recent_message_limit=50,
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
    )
    try:
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="ground",
            content="please continue",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )

        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="pulse", name="system")],
            "context": "objective",
            "next_step": "",
        }
        inject_inbox_before_pulse(state, project_id=project_id, agent_id=agent_id)

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        brain = _CaptureBrain()
        agent.brain = brain
        agent.process(state)

        assert "marked handled automatically" in brain.seen
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
