from __future__ import annotations

import pytest

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def test_runtime_policy_accepts_only_react_and_freeform():
    project_id = "unit_runtime_policy_default"
    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        phase_strategy="react_graph",
        agent_settings={"alpha": AgentModelConfig(model="stepfun/step-3.5-flash:free")},
    )
    try:
        assert resolve_phase_strategy(project_id, "alpha") == "react_graph"
        runtime_config.projects[project_id].agent_settings["alpha"].phase_strategy = "freeform"
        assert resolve_phase_strategy(project_id, "alpha") == "freeform"
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old


def test_runtime_policy_rejects_legacy_phase_strategy():
    project_id = "unit_runtime_policy_invalid"
    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        phase_strategy="react_graph",
        agent_settings={"alpha": AgentModelConfig(model="stepfun/step-3.5-flash:free")},
    )
    runtime_config.projects[project_id].phase_strategy = "strict" + "_triad"  # type: ignore[assignment]
    try:
        with pytest.raises(ValueError):
            resolve_phase_strategy(project_id, "alpha")
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
