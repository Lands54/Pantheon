from pathlib import Path
import shutil

from gods.interaction.facade import submit_hermes_notice
from gods.iris import facade as iris_facade


def test_interaction_hermes_notice_batches_targets():
    project_id = "unit_interaction_hermes_notice"
    try:
        sent = submit_hermes_notice(
            project_id=project_id,
            targets=["a", "b"],
            sender_id="Hermes",
            title="Contract Commit Notice",
            content="contract committed",
            msg_type="contract_notice",
            trigger_pulse=False,
            priority=80,
        )
        assert sent == ["a", "b"]
        assert iris_facade.has_pending(project_id, "a") is True
        assert iris_facade.has_pending(project_id, "b") is True
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

