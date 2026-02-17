from pathlib import Path
import shutil

from gods.angelia.pulse.queue import enqueue_pulse_event, pick_pulse_events


def test_pulse_queue_priority_and_stable_pick_order():
    project_id = "unit_pulse_priority"
    try:
        # lower priority first in time
        enqueue_pulse_event(project_id, "a", "timer", priority=10, payload={"x": 1})
        enqueue_pulse_event(project_id, "b", "manual", priority=80, payload={"x": 2})
        enqueue_pulse_event(project_id, "c", "inbox_event", priority=100, payload={"x": 3})

        picked = pick_pulse_events(project_id, ["a", "b", "c"], batch_size=3)
        assert [p.agent_id for p in picked] == ["c", "b", "a"]
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
