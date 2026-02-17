# @whitebox-reason: verify runtime.detach internal event emission creates interaction notice.
from pathlib import Path
import shutil

from gods.runtime.detach.events import emit_detach_event
from gods.iris import facade as iris_facade


def test_detach_event_emits_interaction_notice():
    project_id = "unit_detach_event_notice"
    try:
        emit_detach_event(
            project_id=project_id,
            event_type="detach_started_event",
            payload={"job_id": "j1", "agent_id": "a", "status": "running"},
            dedupe_key="d1",
        )
        assert iris_facade.has_pending(project_id, "a") is True
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

