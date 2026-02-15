from pathlib import Path
import shutil

from api import scheduler
from gods.pulse.queue import enqueue_pulse_event, mark_pulse_event_done


def test_scheduler_priority_without_permanent_starvation():
    project_id = "unit_scheduler_no_starvation"
    try:
        enqueue_pulse_event(project_id, "a", "timer", priority=10, payload={})
        hi = enqueue_pulse_event(project_id, "a", "inbox_event", priority=100, payload={"k": 1})

        first = scheduler.pick_pulse_batch(project_id, ["a"], batch_size=1)
        assert first and first[0][1] == "inbox_event"
        mark_pulse_event_done(project_id, first[0][2], dropped=False)

        second = scheduler.pick_pulse_batch(project_id, ["a"], batch_size=1)
        assert second
        assert second[0][1] in {"timer", "idle_heartbeat"}
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
