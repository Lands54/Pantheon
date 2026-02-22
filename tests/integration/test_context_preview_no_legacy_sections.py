from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from api.app import app
from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config

client = TestClient(app)


class _FakeBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        return AIMessage(content="done", tool_calls=[])


def test_context_preview_no_legacy_sections():
    pid = "it_context_preview_no_legacy_sections"
    aid = "alpha"
    agent_dir = Path("projects") / pid / "agents" / aid
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / pid / "mnemosyne" / "agent_profiles" / f"{aid}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# alpha", encoding="utf-8")

    old = runtime_config.projects.get(pid)
    runtime_config.projects[pid] = ProjectConfig(
        active_agents=[aid],
        context_strategy="structured_v1",
        agent_settings={aid: AgentModelConfig(disabled_tools=[])},
    )
    old_cur = runtime_config.current_project
    runtime_config.current_project = pid
    try:
        agent = GodAgent(agent_id=aid, project_id=pid)
        agent.brain = _FakeBrain()
        state = {
            "project_id": pid,
            "messages": [HumanMessage(content="start", name="h")],
            "context": "objective",
            "next_step": "",
        }
        agent.process(state)

        snap = client.get(f"/projects/{pid}/context/snapshot", params={"agent_id": aid, "since_intent_seq": 0})
        assert snap.status_code == 200
        payload = snap.json() or {}
        assert payload.get("mode") == "pulse_ledger"
        assert isinstance(payload.get("pulses"), list)
    finally:
        runtime_config.current_project = old_cur
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
        shutil.rmtree(Path("projects") / pid, ignore_errors=True)
