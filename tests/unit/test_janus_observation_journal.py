import shutil
from pathlib import Path

from gods.mnemosyne.facade import list_observations, observations_path, record_observation, ObservationRecord


def test_observation_journal_write_and_read():
    pid = "unit_janus_obs"
    aid = "agent"
    base = Path("projects") / pid
    shutil.rmtree(base, ignore_errors=True)
    try:
        record_observation(
            ObservationRecord(
                project_id=pid,
                agent_id=aid,
                tool_name="run_command",
                args_summary="python app.py",
                result_summary="ok",
                status="ok",
                timestamp=1.23,
            )
        )
        p = observations_path(pid, aid)
        assert p.exists()
        rows = list_observations(pid, aid, limit=10)
        assert rows
        assert rows[-1]["tool"] == "run_command"
        assert rows[-1]["status"] == "ok"
    finally:
        shutil.rmtree(base, ignore_errors=True)
