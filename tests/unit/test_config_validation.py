from gods.config import ProjectConfig, runtime_config
from gods.angelia import policy


def test_angelia_timer_idle_is_single_source():
    pid = "unit_timer_ssot"
    old = runtime_config.projects.get(pid)
    try:
        runtime_config.projects[pid] = ProjectConfig(
            queue_idle_heartbeat_sec=999,
            angelia_timer_idle_sec=17,
        )
        assert policy.timer_idle_sec(pid) == 17
    finally:
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
