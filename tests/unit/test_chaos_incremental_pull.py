from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from gods.agents.base import GodAgent
from gods.chaos.snapshot import pull_incremental_materials
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos incremental test", encoding="utf-8")


def test_pull_incremental_materials_updates_state(monkeypatch):
    project_id = "unit_chaos_incremental"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos inc",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )

    monkeypatch.setattr("gods.chaos.snapshot.latest_intent_seq", lambda pid, aid: 5)
    
    fake_intents = [
        SimpleNamespace(
            intent_key="inbox.received.unread",
            project_id=project_id,
            agent_id=agent_id,
            source_kind="inbox",
            payload={"message_id": "m1"},
            intent_seq=4,
        ),
        SimpleNamespace(
            intent_key="event.manual",
            project_id=project_id,
            agent_id=agent_id,
            source_kind="event",
            payload={"reason": "manual"},
            intent_seq=5,
            fallback_text="test trigger",
            intent_id="e1",
        )
    ]
    
    monkeypatch.setattr(
        "gods.chaos.snapshot.fetch_intents_between",
        lambda pid, aid, start, end: fake_intents if start <= 5 else [],
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "__chaos_synced_seq": 3,
            "cards": [],
        }
        patch = pull_incremental_materials(agent, state)
        
        # Verify cards collection instead of legacy buckets
        assert len(state["cards"]) == 2
        
        # Verify card semantics
        cards = state["cards"]
        kinds = [c["meta"]["source_kind"] for c in cards]
        keys = [c["meta"]["intent_key"] for c in cards]
        
        assert "inbox" in kinds
        assert "event" in kinds
        assert "inbox.received.unread" in keys
        assert "event.manual" in keys

        inc = ((patch or {}).get("runtime_meta", {}) or {}).get("incremental_pull", {})
        assert inc.get("new_trigger_count") == 1
        assert inc.get("new_mailbox_count") == 1
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_pull_incremental_materials_includes_to_chronicle_only_intents(monkeypatch):
    project_id = "unit_chaos_incremental_chronicle_only"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos inc chronicle",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )

    monkeypatch.setattr("gods.chaos.snapshot.latest_intent_seq", lambda pid, aid: 2)
    monkeypatch.setattr(
        "gods.chaos.snapshot.fetch_intents_between",
        lambda pid, aid, start, end: [
            SimpleNamespace(
                intent_key="tool.read.ok",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="tool",
                payload={"tool_name": "read"},
                intent_seq=2,
                fallback_text="[[ACTION]] read (ok) -> test",
                intent_id="solo:2",
            )
        ],
    )
    monkeypatch.setattr(
        "gods.mnemosyne.semantics.semantics_service.get_policy",
        lambda key: {"to_llm_context": False, "to_chronicle": True} if key == "tool.read.ok" else {"to_llm_context": False, "to_chronicle": False},
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "__chaos_synced_seq": 1,
            "cards": [],
        }
        _ = pull_incremental_materials(agent, state)
        assert len(state["cards"]) == 1
        c = state["cards"][0]
        assert c["meta"]["intent_key"] == "tool.read.ok"
        assert c["meta"]["source_kind"] == "tool"
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
