from gods.config import ProjectConfig, runtime_config
from gods.metis.snapshot import resolve_refresh_mode


def test_sequential_v1_forces_pulse_refresh_mode():
    pid = "unit_pulse_refresh"
    aid = "alpha"
    old = runtime_config.projects.get(pid)
    try:
        runtime_config.projects[pid] = ProjectConfig(
            context_strategy="sequential_v1",
            metis_refresh_mode="node",
            agent_settings={aid: {"model": "stepfun/step-3.5-flash:free", "metis_refresh_mode": "node"}},
        )
        mode = resolve_refresh_mode({"project_id": pid, "agent_id": aid})
        assert mode == "pulse"
    finally:
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
