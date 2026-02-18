from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.base import GodAgent
from gods.chaos.snapshot import build_resource_snapshot
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.metis.snapshot import build_runtime_envelope


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos snapshot test", encoding="utf-8")


def test_chaos_snapshot_contains_core_materials():
    project_id = "unit_chaos_snapshot"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos snapshot",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "strategy": "react_graph",
            "messages": [],
            "mailbox": [],
            "triggers": [],
            "__pulse_meta": {"pulse_id": "p1"},
        }
        snapshot = build_resource_snapshot(agent, state, strategy="react_graph")
        assert snapshot.project_id == project_id
        assert snapshot.agent_id == agent_id
        assert isinstance(snapshot.tool_catalog, list) and snapshot.tool_catalog
        assert "mailbox_intents_count" in snapshot.memory
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_runtime_envelope_contains_strategy_policy():
    project_id = "unit_chaos_envelope"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos envelope",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {"project_id": project_id, "agent_id": agent_id, "strategy": "react_graph", "messages": []}
        envelope = build_runtime_envelope(agent, state, strategy="react_graph")
        assert envelope.strategy == "react_graph"
        assert envelope.policy.get("phases") == ["global"]
        assert envelope.trace.get("provider") == "gods.metis.snapshot"
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
