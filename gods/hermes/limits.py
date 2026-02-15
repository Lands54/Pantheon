"""Hermes in-memory concurrency and rate limits."""
from __future__ import annotations

import threading
import time
from collections import deque

from gods.hermes.errors import HermesError, HERMES_RATE_LIMITED, HERMES_BUSY


class HermesLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._running: dict[str, int] = {}
        self._calls: dict[str, deque] = {}

    def _key(self, project_id: str, name: str, version: str) -> str:
        return f"{project_id}:{name}:{version}"

    def acquire(self, project_id: str, name: str, version: str, max_concurrency: int, rate_per_minute: int):
        key = self._key(project_id, name, version)
        now = time.time()
        with self._lock:
            q = self._calls.setdefault(key, deque())
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= max(1, rate_per_minute):
                raise HermesError(HERMES_RATE_LIMITED, f"Rate limit exceeded for {name}@{version}", retryable=True)

            running = self._running.get(key, 0)
            if running >= max(1, max_concurrency):
                raise HermesError(HERMES_BUSY, f"Concurrency limit exceeded for {name}@{version}", retryable=True)

            self._running[key] = running + 1
            q.append(now)

    def release(self, project_id: str, name: str, version: str):
        key = self._key(project_id, name, version)
        with self._lock:
            running = self._running.get(key, 0)
            if running <= 1:
                self._running.pop(key, None)
            else:
                self._running[key] = running - 1
