from pathlib import Path
import shutil

from gods.interaction.facade import submit_detach_notice
from gods.iris import facade as iris_facade


def test_interaction_detach_notice_writes_mailbox():
    project_id = "unit_interaction_detach_notice"
    try:
        row = submit_detach_notice(
            project_id=project_id,
            agent_id="runner",
            title="Detach Started",
            content="job started",
            trigger_pulse=False,
        )
        assert row["event_type"] == "interaction.detach.notice"
        assert row["state"] == "done"
        assert iris_facade.has_pending(project_id, "runner") is True
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

