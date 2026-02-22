from __future__ import annotations

import json
import shutil
import uuid

from gods import events as events_bus
from gods.angelia import sync_council
from gods.paths import project_dir, runtime_dir


def _new_pid() -> str:
    return f"ut_robert_{uuid.uuid4().hex[:8]}"


def _activate(pid: str):
    rt = runtime_dir(pid)
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "angelia_agents.json").write_text(
        json.dumps({"a1": {"run_state": "idle"}, "a2": {"run_state": "idle"}}),
        encoding="utf-8",
    )


def test_motion_vote_resolution_flow():
    pid = _new_pid()
    pdir = project_dir(pid)
    try:
        sync_council.start_session(pid, title="议题", content="内容", participants=["a1", "a2"], cycles=1)
        sync_council.confirm_participant(pid, "a1")
        sync_council.confirm_participant(pid, "a2")
        _activate(pid)
        sync_council.tick(pid, "a1", has_queued=False)

        st = sync_council.submit_action(pid, actor_id="a1", action_type="motion_submit", payload={"text": "执行接口对齐"})
        assert st["current_motion"]["state"] == "proposed"
        st = sync_council.submit_action(pid, actor_id="a2", action_type="motion_second", payload={})
        assert st["current_motion"]["state"] == "debating"
        st = sync_council.submit_action(pid, actor_id="a1", action_type="procedural_call_question", payload={})
        assert st["current_motion"]["state"] == "voting"
        sync_council.submit_action(pid, actor_id="a1", action_type="vote_cast", payload={"choice": "yes"})
        st = sync_council.submit_action(pid, actor_id="a2", action_type="vote_cast", payload={"choice": "yes"})
        assert st["current_motion"] == {}
        rows = sync_council.list_resolutions(pid, limit=10)
        assert len(rows) >= 1
        assert rows[0]["decision"] in {"adopted", "rejected"}
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_non_council_event_deferred_during_session():
    pid = _new_pid()
    pdir = project_dir(pid)
    try:
        sync_council.start_session(pid, title="议题", content="内容", participants=["a1"], cycles=1)
        sync_council.confirm_participant(pid, "a1")
        _activate(pid)
        sync_council.tick(pid, "a1", has_queued=False)

        evt = events_bus.EventRecord.create(
            project_id=pid,
            domain="angelia",
            event_type="manual",
            priority=80,
            payload={"agent_id": "a1", "reason": "manual"},
        )
        events_bus.append_event(evt)
        decision = sync_council.evaluate_pick_gate(pid, "a1", evt)
        assert decision.allowed is False
        assert decision.defer is True
        sync_council.register_deferred_event(pid, evt.event_id)
        st = sync_council.get_state(pid)
        assert evt.event_id in set(st.get("deferred_event_ids", []))
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
