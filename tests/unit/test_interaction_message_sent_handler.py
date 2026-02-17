from pathlib import Path
import shutil

from gods.interaction.facade import submit_message_event
from gods.iris import facade as iris_facade


def test_interaction_message_sent_writes_mailbox_and_receipt():
    project_id = "unit_interaction_message_sent"
    try:
        ret = submit_message_event(
            project_id=project_id,
            to_id="receiver",
            sender_id="sender",
            title="hello",
            content="payload",
            msg_type="private",
            trigger_pulse=False,
            priority=100,
        )
        assert ret["event_type"] == "interaction.message.sent"
        assert ret["state"] == "done"
        assert iris_facade.has_pending(project_id, "receiver") is True
        rows = iris_facade.list_outbox_receipts(project_id, from_agent_id="sender", to_agent_id="receiver", limit=20)
        assert any(x.title == "hello" for x in rows)
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

