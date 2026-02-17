from pathlib import Path
import shutil

from gods.iris.facade import enqueue_message
from gods.angelia.facade import inject_inbox_after_action_if_any


def test_after_action_interrupt_injects_inbox_message():
    project_id = "unit_interrupt_after_action"
    agent_id = "a"
    try:
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="b",
            title="ping title",
            content="ping",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        state = {"messages": []}
        count = inject_inbox_after_action_if_any(state, project_id, agent_id)
        assert count == 1
        assert state["messages"]
        assert "[INBOX UNREAD]" in str(state["messages"][-1].content)
        assert state.get("__inbox_delivered_ids")
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
