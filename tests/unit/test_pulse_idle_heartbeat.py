from pathlib import Path
import shutil
import time

from api import scheduler
from gods.config import ProjectConfig, runtime_config


def test_idle_heartbeat_enqueued_when_queue_empty(monkeypatch):
    project_id = "unit_idle_heartbeat"
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=["a"],
        queue_idle_heartbeat_sec=60,
    )
    try:
        st = scheduler._get_status(project_id, "a")
        st["status"] = "idle"
        st["next_eligible_at"] = 0.0
        st["last_timer_emit_at"] = 0.0

        now = 1000.0
        monkeypatch.setattr(scheduler.time, "time", lambda: now)

        batch = scheduler.pick_pulse_batch(project_id, ["a"], batch_size=1)
        assert len(batch) == 1
        assert batch[0][0] == "a"
        assert batch[0][1] == "idle_heartbeat"
    finally:
        runtime_config.projects.pop(project_id, None)
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
