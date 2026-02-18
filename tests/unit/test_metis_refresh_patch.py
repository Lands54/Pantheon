from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.metis.snapshot import refresh_runtime_envelope


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nmetis refresh patch test", encoding="utf-8")


def test_refresh_runtime_envelope_supports_snapshot_patch():
    project_id = "unit_metis_refresh_patch"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="metis refresh patch",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {"project_id": project_id, "agent_id": agent_id, "strategy": "react_graph", "messages": []}
        env = refresh_runtime_envelope(
            agent,
            state,
            reason="unit_test",
            snapshot_patch={"runtime_meta": {"patched": True}},
        )
        assert env.resource_snapshot.runtime_meta.get("patched") is True
        assert env.trace.get("refresh_reason") == "unit_test"
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
