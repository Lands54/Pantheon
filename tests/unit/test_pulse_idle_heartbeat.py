from pathlib import Path
import shutil

from gods.config import ProjectConfig, runtime_config
from gods.angelia.facade import angelia_supervisor
from gods.angelia import store


def test_idle_heartbeat_enqueued_when_queue_empty(monkeypatch):
    project_id = "unit_idle_heartbeat"
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=["a"],
        queue_idle_heartbeat_sec=60,
        angelia_timer_enabled=True,
        angelia_timer_idle_sec=60,
    )
    try:
        monkeypatch.setattr(angelia_supervisor, "_ensure_worker", lambda *_args, **_kwargs: None)
        ret = angelia_supervisor.tick_timer_once(project_id)
        assert int(ret.get("emitted", 0)) == 1
        rows = store.list_events(project_id=project_id, agent_id="a", event_type="timer", limit=10)
        assert rows
        assert rows[0].state.value in {"queued", "picked", "processing", "done"}
    finally:
        runtime_config.projects.pop(project_id, None)
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
