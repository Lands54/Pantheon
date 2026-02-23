from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import gods.athena.council_engine as council_engine
from gods.athena import (
    advance_flow_stage,
    finish_flow_run,
    get_flow_run,
    list_flow_runs,
    start_flow_run,
)


def _new_pid() -> str:
    return f"ut_athena_{uuid.uuid4().hex[:8]}"


def test_athena_allows_parallel_disjoint_runs():
    pid = _new_pid()
    pdir = Path("projects") / pid
    shutil.rmtree(pdir, ignore_errors=True)
    try:
        r1 = start_flow_run(
            pid,
            flow_key="explore_contract_loop",
            participants=["a1", "a2"],
            title="flow-A",
        )
        r2 = start_flow_run(
            pid,
            flow_key="explore_contract_loop",
            participants=["a3", "a4"],
            title="flow-B",
        )
        runs = list_flow_runs(pid, include_inactive=True)
        ids = {str(x.get("run_id", "")) for x in runs}
        assert r1["run_id"] in ids
        assert r2["run_id"] in ids
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_athena_rejects_overlap_on_active_runs():
    pid = _new_pid()
    pdir = Path("projects") / pid
    shutil.rmtree(pdir, ignore_errors=True)
    try:
        start_flow_run(
            pid,
            flow_key="explore_contract_loop",
            participants=["a1", "a2"],
            title="flow-A",
        )
        try:
            start_flow_run(
                pid,
                flow_key="explore_contract_loop",
                participants=["a2", "a3"],
                title="flow-B",
            )
            assert False, "expected overlap rejection"
        except ValueError as e:
            assert "overlap" in str(e)
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_athena_stage_advance_and_finish_release_overlap_guard():
    pid = _new_pid()
    pdir = Path("projects") / pid
    shutil.rmtree(pdir, ignore_errors=True)
    try:
        r1 = start_flow_run(
            pid,
            flow_key="explore_contract_loop",
            participants=["a1", "a2"],
            title="flow-A",
        )
        rid = str(r1["run_id"])
        r1 = advance_flow_stage(pid, run_id=rid, next_stage="contract", actor_id="human.overseer")
        assert r1["current_stage"] == "contract"

        r1 = finish_flow_run(pid, run_id=rid, status="completed", actor_id="human.overseer")
        assert r1["status"] == "completed"

        # now overlap is allowed because the previous run is inactive
        r2 = start_flow_run(
            pid,
            flow_key="explore_contract_loop",
            participants=["a2", "a3"],
            title="flow-B",
        )
        assert r2["status"] == "active"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_athena_roberts_start_hook(monkeypatch):
    pid = _new_pid()
    pdir = Path("projects") / pid
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    calls: dict[str, int] = {"start": 0}

    def _fake_start(project_id, *, title, content, participants, cycles, initiator, rules_profile, agenda, timeouts):
        assert project_id == pid
        calls["start"] += 1
        return {
            "session_id": "sess_ut_1",
            "phase": "collecting",
            "participants": participants,
            "title": title,
        }

    def _fake_get(project_id):
        assert project_id == pid
        return {"session_id": "sess_ut_1", "phase": "collecting", "participants": ["a1", "a2"], "enabled": True}

    monkeypatch.setattr(council_engine, "start_session", _fake_start)
    monkeypatch.setattr(council_engine, "get_state", _fake_get)
    try:
        row = start_flow_run(
            pid,
            flow_key="roberts_council",
            participants=["a1", "a2"],
            title="council",
            config={"content": "议题", "cycles": 2},
        )
        assert calls["start"] == 1
        assert row["flow_key"] == "roberts_council"
        assert row["config"]["roberts_session_id"] == "sess_ut_1"
        got = get_flow_run(pid, row["run_id"])
        assert got and got["current_stage"] == "collecting"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_athena_roberts_finish_hook_abort(monkeypatch):
    pid = _new_pid()
    pdir = Path("projects") / pid
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    calls: dict[str, int] = {"start": 0, "terminate": 0}

    def _fake_start(project_id, *, title, content, participants, cycles, initiator, rules_profile, agenda, timeouts):
        calls["start"] += 1
        return {"session_id": "sess_ut_2", "phase": "in_session"}

    def _fake_get(project_id):
        return {"session_id": "sess_ut_2", "phase": "aborted", "enabled": False}

    def _fake_chair(project_id, *, action, actor_id="human.overseer"):
        if action == "terminate":
            calls["terminate"] += 1
        return {"phase": "aborted", "enabled": False}

    monkeypatch.setattr(council_engine, "start_session", _fake_start)
    monkeypatch.setattr(council_engine, "get_state", _fake_get)
    monkeypatch.setattr(council_engine, "chair_action", _fake_chair)
    try:
        row = start_flow_run(pid, flow_key="roberts_council", participants=["a1", "a2"], title="council")
        out = finish_flow_run(pid, run_id=row["run_id"], status="aborted")
        assert calls["start"] == 1
        assert calls["terminate"] == 1
        assert out["status"] == "aborted"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
