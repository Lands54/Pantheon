from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gods.agents.base import GodAgent
from gods.chaos.snapshot import build_resource_snapshot
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos card buckets test", encoding="utf-8")


def test_chaos_static_materials_contract():
    project_id = "unit_chaos_card_buckets"
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
        materials = snapshot.context_materials
        assert str(materials.profile or "").strip()
        assert isinstance(materials.directives, str)
        assert str(materials.task_state or "").strip()
        assert str(materials.tools or "").strip()
        assert str(materials.inbox_hint or "").strip()
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_chaos_context_materials_not_mapping():
    project_id = "unit_chaos_materials_shape"
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
        snapshot = build_resource_snapshot(agent, {"project_id": project_id, "agent_id": agent_id}, strategy="react_graph")
        with pytest.raises(TypeError):
            dict(snapshot.context_materials)  # type: ignore[arg-type]
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
