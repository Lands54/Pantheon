from __future__ import annotations

import shutil
from pathlib import Path

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
    
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "__chaos_synced_seq": 3,
        }
        patch = pull_incremental_materials(agent, state)

        inc = ((patch or {}).get("runtime_meta", {}) or {}).get("incremental_pull", {})
        assert inc.get("new_trigger_count") == 0
        assert inc.get("new_mailbox_count") == 0
        assert int(inc.get("last_synced_seq", 0)) == 3
        assert int(inc.get("current_latest_seq", 0)) == 5
        assert int(state.get("__chaos_synced_seq", 0)) == 5
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_pull_incremental_materials_is_noop_for_cards(monkeypatch):
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
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "__chaos_synced_seq": 1,
        }
        patch = pull_incremental_materials(agent, state)
        inc = ((patch or {}).get("runtime_meta", {}) or {}).get("incremental_pull", {})
        assert int(inc.get("last_synced_seq", 0)) == 1
        assert int(inc.get("current_latest_seq", 0)) == 2
        assert "cards" not in state
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
