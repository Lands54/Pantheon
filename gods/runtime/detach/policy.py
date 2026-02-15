"""Detach queue policy helpers (limits + FIFO victim selection)."""
from __future__ import annotations

from gods.runtime.detach.models import DetachJob, DetachStatus


def count_running(jobs: list[DetachJob], agent_id: str | None = None) -> int:
    n = 0
    for job in jobs:
        if job.status != DetachStatus.RUNNING:
            continue
        if agent_id and job.agent_id != agent_id:
            continue
        n += 1
    return n


def select_fifo_victims(
    jobs: list[DetachJob],
    *,
    max_running_project: int,
    max_running_agent: int,
    agent_id: str,
) -> list[DetachJob]:
    running = [j for j in jobs if j.status == DetachStatus.RUNNING]
    running.sort(key=lambda x: (x.started_at or x.created_at or 0.0))

    victims: list[DetachJob] = []

    while count_running(running, None) > max_running_project:
        if not running:
            break
        v = running.pop(0)
        victims.append(v)

    # recompute with project victims removed
    filtered = [j for j in running if j.agent_id == agent_id]
    while len(filtered) > max_running_agent:
        v = filtered.pop(0)
        victims.append(v)
        running = [x for x in running if x.job_id != v.job_id]

    # dedupe while preserving order
    seen = set()
    out = []
    for v in victims:
        if v.job_id in seen:
            continue
        seen.add(v.job_id)
        out.append(v)
    return out
