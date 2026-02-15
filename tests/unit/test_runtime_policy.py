from __future__ import annotations

from gods.agents.runtime_policy import resolve_phase_mode_enabled, resolve_phase_strategy
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def test_runtime_policy_project_default_when_no_agent_override():
    project_id = "unit_runtime_policy_default"
    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        phase_mode_enabled=True,
        phase_strategy="iterative_action",
        agent_settings={"alpha": AgentModelConfig(model="stepfun/step-3.5-flash:free")},
    )
    try:
        assert resolve_phase_mode_enabled(project_id, "alpha") is True
        assert resolve_phase_strategy(project_id, "alpha") == "iterative_action"
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old


def test_runtime_policy_agent_override_wins():
    project_id = "unit_runtime_policy_override"
    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        phase_mode_enabled=True,
        phase_strategy="strict_triad",
        agent_settings={
            "alpha": AgentModelConfig(
                model="stepfun/step-3.5-flash:free",
                phase_mode_enabled=False,
                phase_strategy="freeform",
            )
        },
    )
    try:
        assert resolve_phase_mode_enabled(project_id, "alpha") is False
        assert resolve_phase_strategy(project_id, "alpha") == "freeform"
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
