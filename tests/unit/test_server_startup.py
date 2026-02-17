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
