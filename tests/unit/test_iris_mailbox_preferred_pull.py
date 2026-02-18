from __future__ import annotations

import shutil
from pathlib import Path

from gods.iris import facade as iris_facade


def _first_received_message_id(intents: list) -> str:
    for it in intents:
        key = str(getattr(it, "intent_key", "") or "")
        if key.startswith("inbox.received") or key.startswith("inbox.notice"):
            payload = dict(getattr(it, "payload", {}) or {})
            return str(payload.get("message_id", "") or "")
    return ""


def test_fetch_mailbox_intents_prefers_event_ids_without_fallback():
    project_id = "unit_iris_preferred_pull"
    agent_id = "alpha"
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        first = iris_facade.enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="s1",
            title="msg-1",
            content="c1",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        second = iris_facade.enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="s2",
            title="msg-2",
            content="c2",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        id1 = str(first.get("mail_event_id", "") or "")
        id2 = str(second.get("mail_event_id", "") or "")
        assert id1 and id2 and id1 != id2

        intents = iris_facade.fetch_mailbox_intents(
            project_id=project_id,
            agent_id=agent_id,
            budget=1,
            preferred_event_ids=[id2],
        )
        assert _first_received_message_id(intents) == id2

        intents_miss = iris_facade.fetch_mailbox_intents(
            project_id=project_id,
            agent_id=agent_id,
            budget=1,
            preferred_event_ids=["not_exists"],
        )
        assert _first_received_message_id(intents_miss) == ""
    finally:
        shutil.rmtree(base, ignore_errors=True)
