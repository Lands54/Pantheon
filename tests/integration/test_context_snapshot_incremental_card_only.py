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


def test_context_snapshot_incremental_card_only():
    pid = "it_context_snapshot_incremental_card_only"
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
        for i in range(2):
            state = {
                "project_id": pid,
                "messages": [HumanMessage(content=f"start-{i}", name="h")],
                "context": "objective",
                "next_step": "",
            }
            agent.process(state)

        full = client.get(f"/projects/{pid}/context/snapshot", params={"agent_id": aid, "since_intent_seq": 0})
        assert full.status_code == 200
        d0 = full.json()
        assert d0.get("available") is True
        assert d0.get("mode") == "full"
        cards = list(d0.get("upsert_cards", []) or [])
        assert cards
        assert all("card_id" in c and "kind" in c and "text" in c for c in cards)
        assert "chronicle" not in d0
        assert "context_index_rendered" not in d0

        base = int(d0.get("base_intent_seq", 0) or 0)
        delta = client.get(f"/projects/{pid}/context/snapshot", params={"agent_id": aid, "since_intent_seq": max(1, base)})
        assert delta.status_code == 200
        d1 = delta.json()
        assert d1.get("available") is True
        assert d1.get("mode") == "delta"
        assert isinstance(d1.get("upsert_cards"), list)
        assert isinstance(d1.get("remove_card_ids"), list)
    finally:
        runtime_config.current_project = old_cur
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
        shutil.rmtree(Path("projects") / pid, ignore_errors=True)

