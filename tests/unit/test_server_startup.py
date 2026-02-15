import asyncio

from api.services.simulation_service import simulation_service
from gods.config import ProjectConfig
from gods.config import runtime_config


def test_pause_all_projects_on_startup(monkeypatch):
    original_states = {pid: proj.simulation_enabled for pid, proj in runtime_config.projects.items()}

    save_calls = {"count": 0}

    def fake_save():
        save_calls["count"] += 1

    monkeypatch.setattr(type(runtime_config), "save", lambda self: fake_save())

    try:
        for proj in runtime_config.projects.values():
            proj.simulation_enabled = True

        changed = simulation_service.pause_all_projects_on_startup()
        assert changed == len(runtime_config.projects)
        assert save_calls["count"] == 1
        assert all(not proj.simulation_enabled for proj in runtime_config.projects.values())
    finally:
        for pid, enabled in original_states.items():
            runtime_config.projects[pid].simulation_enabled = enabled


def test_pulse_once_auto_stops_project_when_docker_unavailable(monkeypatch):
    pid = "unit_docker_guard_project"
    old = runtime_config.projects.get(pid)
    old_current = runtime_config.current_project
    try:
        runtime_config.projects[pid] = ProjectConfig(
            simulation_enabled=True,
            active_agents=["genesis"],
            command_executor="docker",
            docker_enabled=True,
        )
        runtime_config.current_project = pid

        monkeypatch.setattr(simulation_service._docker, "docker_available", lambda: (False, "daemon down"))
        out = asyncio.run(simulation_service.pulse_once())
        assert out.get("triggered") == 0
        assert "docker_unavailable" in str(out.get("error", ""))
        assert runtime_config.projects[pid].simulation_enabled is False
    finally:
        runtime_config.current_project = old_current
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
