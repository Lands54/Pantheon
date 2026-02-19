from pathlib import Path
import shutil
import time
from gods.angelia import store
from gods.angelia import policy
from gods.config import ProjectConfig, runtime_config


def test_angelia_priority_without_permanent_starvation():
    project_id = "unit_scheduler_no_starvation"
    try:
        now = time.time() + 1.0
        store.enqueue_event(
            project_id=project_id,
            agent_id="a",
            event_type="timer",
            priority=10,
            payload={},
            dedupe_key="",
            max_attempts=3,
            dedupe_window_sec=0,
        )
        store.enqueue_event(
            project_id=project_id,
            agent_id="a",
            event_type="mail_event",
            priority=100,
            payload={"k": 1, "mail_event_id": "x"},
            dedupe_key="",
            max_attempts=3,
            dedupe_window_sec=0,
        )

        first = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=now,
            cooldown_until=0.0,
            preempt_types={"mail_event", "manual"},
        )
        assert first is not None
        assert first.event_type == "mail_event"
        store.mark_done(project_id, first.event_id)

        second = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=now,
            cooldown_until=0.0,
            preempt_types={"mail_event", "manual"},
        )
        assert second is not None
        assert second.event_type == "timer"
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_angelia_cooldown_force_pick_after_threshold():
    project_id = "unit_scheduler_force_pick_after_threshold"
    try:
        created_at = time.time()
        store.enqueue_event(
            project_id=project_id,
            agent_id="a",
            event_type="system",
            priority=60,
            payload={},
            dedupe_key="",
            max_attempts=3,
            dedupe_window_sec=0,
        )
        cooldown_until = created_at + 120.0

        early = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=created_at + 20.0,
            cooldown_until=cooldown_until,
            preempt_types={"mail_event", "manual"},
            force_after_sec=30.0,
        )
        assert early is None

        late = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=created_at + 40.0,
            cooldown_until=cooldown_until,
            preempt_types={"mail_event", "manual"},
            force_after_sec=30.0,
        )
        assert late is not None
        assert late.event_type == "system"
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_angelia_preempt_types_follow_config_ssot():
    project_id = "unit_scheduler_preempt_ssot"
    old = runtime_config.projects.get(project_id)
    try:
        runtime_config.projects[project_id] = ProjectConfig(
            name="ssot",
            angelia_cooldown_preempt_types=["manual"],
        )
        preempt = policy.cooldown_preempt_types(project_id)
        assert preempt == {"manual"}
        assert "detach_failed_event" not in preempt
        assert "detach_lost_event" not in preempt
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
