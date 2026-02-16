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
            return dict(self._counters)


angelia_metrics = AngeliaMetrics()
