from pathlib import Path
import shutil
import time
from gods.angelia import store


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
            event_type="inbox_event",
            priority=100,
            payload={"k": 1, "inbox_event_id": "x"},
            dedupe_key="",
            max_attempts=3,
            dedupe_window_sec=0,
        )

        first = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=now,
            cooldown_until=0.0,
            preempt_types={"inbox_event", "manual"},
        )
        assert first is not None
        assert first.event_type == "inbox_event"
        store.mark_done(project_id, first.event_id)

        second = store.pick_next_event(
            project_id=project_id,
            agent_id="a",
            now=now,
            cooldown_until=0.0,
            preempt_types={"inbox_event", "manual"},
        )
        assert second is not None
        assert second.event_type == "timer"
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
