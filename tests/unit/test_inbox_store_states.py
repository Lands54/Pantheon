from pathlib import Path
import shutil

from gods.iris.facade import InboxMessageState
from gods.iris.facade import (
    enqueue_inbox_event,
    list_inbox_events,
    transition_inbox_state,
)


def test_inbox_state_transitions_and_invalid_transition_rejected():
    project_id = "unit_inbox_states"
    try:
        ev = enqueue_inbox_event(
            project_id=project_id,
            agent_id="a",
            sender="s",
            title="hello",
            content="hello",
            msg_type="private",
        )
        ok1 = transition_inbox_state(project_id, ev.event_id, InboxMessageState.DELIVERED)
        assert ok1 is True

        rows = list_inbox_events(project_id, agent_id="a", limit=10)
        assert rows[-1].state == InboxMessageState.DELIVERED

        # invalid: delivered -> deferred is forbidden
        ok2 = transition_inbox_state(project_id, ev.event_id, InboxMessageState.DEFERRED)
        assert ok2 is False

        # valid: delivered -> handled
        ok3 = transition_inbox_state(project_id, ev.event_id, InboxMessageState.HANDLED)
        assert ok3 is True
        rows2 = list_inbox_events(project_id, agent_id="a", limit=10)
        assert rows2[-1].state == InboxMessageState.HANDLED
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
