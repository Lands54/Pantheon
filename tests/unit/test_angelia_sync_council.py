from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from gods.angelia import sync_council
from gods.paths import project_dir, runtime_dir


def _new_pid() -> str:
    return f"ut_sync_{uuid.uuid4().hex[:8]}"


def test_sync_council_collecting_to_in_session_transition():
    pid = _new_pid()
    pdir = project_dir(pid)
    try:
        st = sync_council.start_session(
            pid,
            title="t",
            content="c",
            participants=["a1", "a2"],
            cycles=2,
        )
        assert st["phase"] == "collecting"
        st = sync_council.confirm_participant(pid, "a1")
        assert st["phase"] == "collecting"
        st = sync_council.confirm_participant(pid, "a2")
        assert st["phase"] == "draining"

        # Simulate all participants not running.
        rt = runtime_dir(pid)
        (rt / "angelia_agents.json").write_text(
            json.dumps(
                {
                    "a1": {"run_state": "idle"},
                    "a2": {"run_state": "cooldown"},
                }
            ),
            encoding="utf-8",
        )
        st = sync_council.tick(pid, "a1", has_queued=False)
        assert st["phase"] == "in_session"
        assert st["current_speaker"] == "a1"
        assert int(st["cycles_left"]) == 2
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_sync_council_in_session_advance_and_finish():
    pid = _new_pid()
    pdir = project_dir(pid)
    try:
        sync_council.start_session(
            pid,
            title="t",
            content="c",
            participants=["a1", "a2"],
            cycles=1,
        )
        sync_council.confirm_participant(pid, "a1")
        sync_council.confirm_participant(pid, "a2")
        rt = runtime_dir(pid)
        (rt / "angelia_agents.json").write_text(
            json.dumps({"a1": {"run_state": "idle"}, "a2": {"run_state": "idle"}}),
            encoding="utf-8",
        )
        st = sync_council.tick(pid, "a1", has_queued=False)
        assert st["phase"] == "in_session"
        d1 = sync_council.evaluate_pick_gate(pid, "a1")
        d2 = sync_council.evaluate_pick_gate(pid, "a2")
        assert d1.allowed is True
        assert d2.allowed is False

        st = sync_council.note_pulse_finished(pid, "a1")
        assert st["phase"] == "in_session"
        assert st["current_speaker"] == "a2"

        st = sync_council.note_pulse_finished(pid, "a2")
        assert st["enabled"] is False
        assert st["phase"] == "completed"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
