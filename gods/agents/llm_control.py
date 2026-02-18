"""Global/project LLM request throttling control plane."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from gods.config import runtime_config


@dataclass(frozen=True)
class LLMLimits:
    enabled: bool
    global_max_concurrency: int
    global_rate_per_minute: int
    project_max_concurrency: int
    project_rate_per_minute: int
    acquire_timeout_sec: float
    retry_interval_sec: float


class LLMControlAcquireTimeout(RuntimeError):
    pass


class LLMControlTicket:
    def __init__(self, plane: "LLMControlPlane", project_id: str, acquired: bool):
        self._plane = plane
        self._project_id = project_id
        self._acquired = acquired
        self._released = False

    def release(self):
        if not self._acquired or self._released:
            return
        self._released = True
        self._plane.release(self._project_id)


class LLMControlPlane:
    def __init__(self):
        self._lock = threading.Lock()
        self._global_running = 0
        self._project_running: dict[str, int] = {}
        self._global_calls: deque[float] = deque()
        self._project_calls: dict[str, deque[float]] = {}

    @staticmethod
    def _resolve_limits(project_id: str) -> LLMLimits:
        proj = getattr(runtime_config, "projects", {}).get(project_id)
        enabled = bool(getattr(proj, "llm_control_enabled", True) if proj else True)
        global_max_concurrency = int(getattr(proj, "llm_global_max_concurrency", 8) if proj else 8)
        global_rate_per_minute = int(getattr(proj, "llm_global_rate_per_minute", 120) if proj else 120)
        project_max_concurrency = int(getattr(proj, "llm_project_max_concurrency", 4) if proj else 4)
        project_rate_per_minute = int(getattr(proj, "llm_project_rate_per_minute", 60) if proj else 60)
        acquire_timeout_sec = float(getattr(proj, "llm_acquire_timeout_sec", 20) if proj else 20)
        retry_interval_ms = int(getattr(proj, "llm_retry_interval_ms", 100) if proj else 100)
        return LLMLimits(
            enabled=enabled,
            global_max_concurrency=max(1, global_max_concurrency),
            global_rate_per_minute=max(1, global_rate_per_minute),
            project_max_concurrency=max(1, project_max_concurrency),
            project_rate_per_minute=max(1, project_rate_per_minute),
            acquire_timeout_sec=max(0.1, acquire_timeout_sec),
            retry_interval_sec=max(0.01, retry_interval_ms / 1000.0),
        )

    @staticmethod
    def _prune(now: float, q: deque[float]):
        while q and now - q[0] > 60.0:
            q.popleft()

    def acquire(self, project_id: str) -> LLMControlTicket:
        limits = self._resolve_limits(project_id)
        if not limits.enabled:
            return LLMControlTicket(self, project_id, acquired=False)

        deadline = time.time() + limits.acquire_timeout_sec
        while True:
            now = time.time()
            if now > deadline:
                raise LLMControlAcquireTimeout(
                    f"LLM control acquire timeout for project '{project_id}'"
                )
            wait_for = limits.retry_interval_sec
            with self._lock:
                self._prune(now, self._global_calls)
                pq = self._project_calls.setdefault(project_id, deque())
                self._prune(now, pq)
                project_running = self._project_running.get(project_id, 0)

                global_busy = self._global_running >= limits.global_max_concurrency
                project_busy = project_running >= limits.project_max_concurrency
                global_rate_limited = len(self._global_calls) >= limits.global_rate_per_minute
                project_rate_limited = len(pq) >= limits.project_rate_per_minute

                if not (global_busy or project_busy or global_rate_limited or project_rate_limited):
                    self._global_running += 1
                    self._project_running[project_id] = project_running + 1
                    ts = time.time()
                    self._global_calls.append(ts)
                    pq.append(ts)
                    return LLMControlTicket(self, project_id, acquired=True)

                if global_rate_limited and self._global_calls:
                    wait_for = max(wait_for, 60.0 - (now - self._global_calls[0]))
                if project_rate_limited and pq:
                    wait_for = max(wait_for, 60.0 - (now - pq[0]))
            time.sleep(min(wait_for, max(0.01, deadline - now)))

    def release(self, project_id: str):
        with self._lock:
            if self._global_running > 0:
                self._global_running -= 1
            running = self._project_running.get(project_id, 0)
            if running <= 1:
                self._project_running.pop(project_id, None)
            else:
                self._project_running[project_id] = running - 1


llm_control_plane = LLMControlPlane()

