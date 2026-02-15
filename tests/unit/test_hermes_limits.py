from __future__ import annotations

from gods.hermes.errors import HermesError, HERMES_BUSY, HERMES_RATE_LIMITED
from gods.hermes.limits import HermesLimiter


def test_hermes_limits_concurrency_and_rate():
    lim = HermesLimiter()
    project_id = "p"
    name = "n"
    version = "1.0.0"

    lim.acquire(project_id, name, version, max_concurrency=1, rate_per_minute=10)
    try:
        try:
            lim.acquire(project_id, name, version, max_concurrency=1, rate_per_minute=10)
            assert False, "expected busy"
        except HermesError as e:
            assert e.code == HERMES_BUSY
    finally:
        lim.release(project_id, name, version)

    name2 = "n2"
    lim.acquire(project_id, name2, version, max_concurrency=1, rate_per_minute=1)
    lim.release(project_id, name2, version)
    try:
        lim.acquire(project_id, name2, version, max_concurrency=1, rate_per_minute=1)
        assert False, "expected rate limited"
    except HermesError as e:
        assert e.code == HERMES_RATE_LIMITED
