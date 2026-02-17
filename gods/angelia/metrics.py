"""In-process counters for Angelia."""
from __future__ import annotations

import threading
from collections import defaultdict


class AngeliaMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)

    def inc(self, key: str, n: int = 1):
        with self._lock:
            self._counters[str(key)] += int(n)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            snap = dict(self._counters)
        snap.setdefault("EVENT_DUAL_WRITE_COUNT", 0)
        snap.setdefault("MAIL_EVENT_STATE_MISMATCH_COUNT", 0)
        snap.setdefault("QUEUE_STALL_TIMEOUT_RECOVERED_COUNT", 0)
        return snap


angelia_metrics = AngeliaMetrics()
