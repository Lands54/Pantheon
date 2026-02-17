from __future__ import annotations

import shutil
from pathlib import Path

from gods.iris.service import ack_handled, enqueue_message, fetch_inbox_context, list_outbox_receipts


def test_outbox_receipt_status_flow_pending_delivered_handled():
    project_id = "unit_outbox_flow"
    receiver = "receiver"
    sender = "sender"
    try:
        row = enqueue_message(
            project_id=project_id,
            agent_id=receiver,
            sender=sender,
            title="work-update",
            content="hello",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        rows0 = list_outbox_receipts(project_id=project_id, from_agent_id=sender, to_agent_id=receiver, limit=20)
        assert rows0
        assert rows0[0].status.value == "pending"
        assert rows0[0].title == "work-update"

        _, delivered_ids = fetch_inbox_context(project_id=project_id, agent_id=receiver, budget=3)
        assert row["inbox_event_id"] in delivered_ids
        rows1 = list_outbox_receipts(project_id=project_id, from_agent_id=sender, to_agent_id=receiver, limit=20)
        assert any(r.status.value == "delivered" for r in rows1)

        ack_handled(project_id=project_id, event_ids=delivered_ids, agent_id=receiver)
        rows2 = list_outbox_receipts(project_id=project_id, from_agent_id=sender, to_agent_id=receiver, limit=20)
        assert any(r.status.value == "handled" for r in rows2)
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

