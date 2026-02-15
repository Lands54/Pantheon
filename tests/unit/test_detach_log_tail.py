from __future__ import annotations

import shutil
from pathlib import Path

from gods.runtime.detach.store import append_log, read_log_tail


def test_detach_log_tail_cropping():
    project_id = "unit_detach_log_tail"
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        job_id = "job123"
        payload = ("abc123\n" * 3000) + "THE_END\n"
        append_log(project_id, job_id, payload, tail_chars=400)
        tail = read_log_tail(project_id, job_id, tail_chars=400)
        assert "THE_END" in tail
        assert len(tail) <= 400
    finally:
        shutil.rmtree(base, ignore_errors=True)

