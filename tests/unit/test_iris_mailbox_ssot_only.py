from pathlib import Path
import shutil

from gods.iris import facade as iris_facade


def test_mailbox_state_flow_only_in_iris_store():
    project_id = "unit_mailbox_states"
    try:
        ret = iris_facade.enqueue_message(
            project_id=project_id,
            agent_id="a",
            sender="s",
            title="hello",
            content="hello",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        eid = str(ret.get("mail_event_id", ""))
        assert eid

        assert iris_facade.has_pending(project_id=project_id, agent_id="a") is True

        context, delivered_ids = iris_facade.fetch_inbox_context(project_id=project_id, agent_id="a", budget=10)
        assert "[INBOX SUMMARY]" in context
        assert eid in delivered_ids

        iris_facade.ack_handled(project_id=project_id, event_ids=delivered_ids, agent_id="a")
        assert iris_facade.has_pending(project_id=project_id, agent_id="a") is False

        receipts = iris_facade.list_outbox_receipts(project_id=project_id, from_agent_id="s", to_agent_id="a", limit=20)
        target = [r for r in receipts if r.message_id == eid]
        assert target and target[-1].status.value == "handled"
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
