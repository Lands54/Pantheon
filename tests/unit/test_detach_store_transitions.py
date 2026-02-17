from __future__ import annotations

import shutil
from pathlib import Path

from gods.runtime.facade import (
    DetachStatus,
    create_job,
    get_job,
    mark_non_final_as_lost,
    transition_job,
)


def test_detach_store_transitions_and_mark_lost():
    project_id = "unit_detach_store"
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        job = create_job(project_id, "alpha", "echo hello")
        assert job.status == DetachStatus.QUEUED

        running = transition_job(project_id, job.job_id, DetachStatus.RUNNING)
        assert running is not None
        assert running.status == DetachStatus.RUNNING
        assert running.started_at is not None

        stopped = transition_job(project_id, job.job_id, DetachStatus.STOPPED, stop_reason="manual", exit_code=0)
        assert stopped is not None
        assert stopped.status == DetachStatus.STOPPED
        assert stopped.stop_reason == "manual"
        assert stopped.exit_code == 0
        assert stopped.ended_at is not None

        job2 = create_job(project_id, "alpha", "echo second")
        assert job2.status == DetachStatus.QUEUED
        changed = mark_non_final_as_lost(project_id)
        assert changed == 1
        got = get_job(project_id, job2.job_id)
        assert got is not None
        assert got.status == DetachStatus.LOST
        assert got.stop_reason == "startup_lost"
    finally:
        shutil.rmtree(base, ignore_errors=True)
