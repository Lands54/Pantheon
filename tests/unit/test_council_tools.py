from __future__ import annotations

import json
import shutil
import uuid

from gods.angelia import sync_council
from gods.paths import project_dir, runtime_dir
from gods.tools.council import council_action, council_confirm, council_status


def _pid() -> str:
    return f"ut_council_tools_{uuid.uuid4().hex[:8]}"


def test_council_tools_basic_flow():
    pid = _pid()
    pdir = project_dir(pid)
    try:
        sync_council.start_session(pid, title="t", content="c", participants=["a1", "a2"], cycles=1)
        out = council_status.invoke({"caller_id": "a1", "project_id": pid})
        assert "phase=collecting" in out

        out = council_confirm.invoke({"caller_id": "a1", "project_id": pid})
        assert "COUNCIL_CONFIRM" in out
        sync_council.confirm_participant(pid, "a2")

        rt = runtime_dir(pid)
        rt.mkdir(parents=True, exist_ok=True)
        (rt / "angelia_agents.json").write_text(json.dumps({"a1": {"run_state": "idle"}, "a2": {"run_state": "idle"}}), encoding="utf-8")
        sync_council.tick(pid, "a1", has_queued=False)

        out = council_action.invoke({
            "action_type": "motion_submit",
            "payload_json": '{"text":"proposal"}',
            "caller_id": "a1",
            "project_id": pid,
        })
        assert "COUNCIL_ACTION" in out
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
