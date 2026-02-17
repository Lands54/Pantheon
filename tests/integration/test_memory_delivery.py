"""
Integration test: prove memory delivery across pulses is reliable.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import runtime_config, ProjectConfig, AgentModelConfig


class _FakeBrain:
    def __init__(self):
        self.calls = 0
        self.system_prompts: list[str] = []

    def think_with_tools(self, messages, tools, trace_meta=None):
        # Capture exactly what the model receives as system context each pulse.
        self.system_prompts.append(messages[0].content if messages else "")
        if self.calls == 0:
            self.calls += 1
            return AIMessage(
                content="inspect marker",
                tool_calls=[
                    {
                        "id": "tc_mem_1",
                        "name": "list_dir",
                        "args": {"path": "."},
                    }
                ],
            )
        self.calls += 1
        return AIMessage(content="done", tool_calls=[])

    def think(self, context: str, trace_meta=None):
        return "READY_NEXT=YES"


def test_memory_is_delivered_to_next_pulse():
    project_id = "it_memory_delivery"
    agent_id = "carrier"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# carrier\nmemory test", encoding="utf-8")

    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it memory delivery",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(model="stepfun/step-3.5-flash:free", disabled_tools=[])},
        simulation_enabled=False,
        phase_mode_enabled=True,
        phase_single_tool_call=True,
        tool_loop_max=3,
        memory_compact_trigger_tokens=120000,
        memory_compact_strategy="rule_based",
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        fake_brain = _FakeBrain()
        agent.brain = fake_brain

        # Pulse 1: execute one list_dir action and persist memory.
        state1 = {
            "project_id": project_id,
            "messages": [HumanMessage(content="start", name="tester")],
            "context": "memory delivery experiment",
            "next_step": "",
        }
        agent.process(state1)

        mem_text = (Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}.md").read_text(encoding="utf-8")
        assert ("inspect marker" in mem_text) or ("done" in mem_text)

        # Pulse 2: with no tool calls, verify model still receives prior memory in system context.
        state2 = {
            "project_id": project_id,
            "messages": [HumanMessage(content="continue", name="tester")],
            "context": "memory delivery experiment",
            "next_step": "",
        }
        agent.process(state2)

        assert len(fake_brain.system_prompts) >= 2
        second_prompt = fake_brain.system_prompts[-1]
        assert ("inspect marker" in second_prompt) or ("done" in second_prompt)

        # Also verify phase runtime state persistence file exists.
        assert (agent_dir / "runtime_state.json").exists()
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
