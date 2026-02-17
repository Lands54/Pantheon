import shutil
from pathlib import Path

from gods.iris.facade import enqueue_message, fetch_inbox_context
from gods.janus.facade import inbox_digest_path


def test_inbox_context_contains_handled_hint_and_writes_digest():
    pid = "unit_janus_inbox_hint"
    aid = "receiver"
    base = Path("projects") / pid
    shutil.rmtree(base, ignore_errors=True)
    try:
        enqueue_message(
            project_id=pid,
            agent_id=aid,
            sender="sender",
            title="hello-title",
            content="hello",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        text, ids = fetch_inbox_context(pid, aid, budget=3)
        assert ids
        assert "marked handled automatically" in text
        d = inbox_digest_path(pid, aid)
        assert d.exists()
    finally:
        shutil.rmtree(base, ignore_errors=True)
