from __future__ import annotations

from gods.runtime.detach.models import DetachJob, DetachStatus
from gods.runtime.detach.policy import select_fifo_victims


def _job(job_id: str, agent_id: str, started_at: float) -> DetachJob:
    return DetachJob(
        job_id=job_id,
        project_id="p",
        agent_id=agent_id,
        command="echo x",
        created_at=started_at - 1,
        started_at=started_at,
        status=DetachStatus.RUNNING,
    )


def test_detach_fifo_policy_project_and_agent_limits():
    jobs = [
        _job("j1", "a", 10.0),
        _job("j2", "a", 20.0),
        _job("j3", "b", 30.0),
    ]
    victims = select_fifo_victims(
        jobs,
        max_running_project=2,
        max_running_agent=1,
        agent_id="a",
    )
    ids = [v.job_id for v in victims]
    assert "j1" in ids
    assert "j2" not in ids

