"""
Integration test: freeform mode bypasses phase runtime and runs legacy agent<->tool loop.
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

    def think_with_tools(self, messages, tools, trace_meta=None):
        if self.calls == 0:
            self.calls += 1
            return AIMessage(
                content="freeform action",
                tool_calls=[
                    {"id": "ff1", "name": "list_dir", "args": {"path": "."}},
                ],
            )
        self.calls += 1
        return AIMessage(content="freeform done", tool_calls=[])

    def think(self, context: str, trace_meta=None):
        return "READY_NEXT=YES"


def test_freeform_strategy_uses_legacy_loop():
    project_id = "it_freeform_mode"
    agent_id = "solo"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# solo\nfreeform test", encoding="utf-8")

    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it freeform mode",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(model="stepfun/step-3.5-flash:free", disabled_tools=[])},
        simulation_enabled=False,
        phase_strategy="freeform",
        tool_loop_max=3,
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        agent.brain = _FakeBrain()

        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="start", name="tester")],
            "context": "freeform experiment",
            "next_step": "",
        }
        out = agent.process(state)
        assert out["next_step"] == "finish"

        mem_text = (Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}.md").read_text(encoding="utf-8")
        assert "[[ACTION]] list_dir" in mem_text
        runtime_text = (Path("projects") / project_id / "mnemosyne" / "runtime_events" / f"{agent_id}.jsonl").read_text(encoding="utf-8")
        assert "agent.mode.freeform" in runtime_text
        assert not (agent_dir / "runtime_state.json").exists()
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
